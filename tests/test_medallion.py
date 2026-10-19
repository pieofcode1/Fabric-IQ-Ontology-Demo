from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from pyspark.sql import SparkSession
from pyspark.sql import functions as fn

from src.data_generator.generate import build_datasets, load_config, write_csv
from src.data_generator.medallion import (
    BRONZE_NAMES,
    GOLD_SOURCES,
    SPECS,
    build_gold,
    build_silver,
    conform_table,
    validate_evidence,
    validate_silver,
    write_layer,
)
from src.data_generator.validate_scenario import run_validation


@pytest.fixture(scope="module")
def spark() -> Iterator[SparkSession]:
    session = (
        SparkSession.builder.master("local[1]")
        .appName("nimbus-medallion-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture(scope="module")
def bronze(spark: SparkSession) -> dict[str, Any]:
    config = load_config(Path("src/data_generator/config/scenario_config.yaml"))
    config["scale"].update(
        customers=150,
        accounts=100,
        subscriptions=250,
        network_assets=60,
        telemetry_events=500,
        alarms=30,
        incidents=5,
        support_cases=40,
        work_orders=20,
        technicians=20,
        sla_exposure=25,
    )
    datasets = build_datasets(config)
    return {
        name: spark.createDataFrame(
            [
                tuple(None if row.get(column) is None else str(row[column]) for column in rows[0])
                for row in rows
            ],
            ", ".join(f"{column} string" for column in rows[0]),
        ).cache()
        for name, raw_name in BRONZE_NAMES.items()
        if (rows := datasets[f"{raw_name}.csv"])
    }


@pytest.fixture(scope="module")
def silver(bronze: dict[str, Any]) -> dict[str, Any]:
    return build_silver(bronze)


def test_silver_and_gold_reconcile(silver: dict[str, Any]) -> None:
    gold = build_gold(silver)
    assert set(silver) == set(SPECS)
    assert set(GOLD_SOURCES) <= set(gold)
    contracts = yaml.safe_load(Path("data_contracts/silver_gold_tables.yml").read_text())
    assert set(contracts["silver_tables"]) == set(silver)
    assert set(contracts["gold_tables"]) == set(gold)
    model = yaml.safe_load(Path("semantic_model/semantic_model.yml").read_text())
    for table in model["tables"].values():
        assert table["source"] in gold
        assert set(table["columns"]) <= set(gold[table["source"]].columns)
    for target, source in GOLD_SOURCES.items():
        assert gold[target].count() == silver[source].count()
    incident = "INC-2026-ONT-001"
    expected = silver["bridge_incident_service"].where(fn.col("incident_id") == incident).count()
    actual = (
        gold["agg_customer_impact_by_incident"]
        .where(fn.col("incident_id") == incident)
        .agg(fn.sum("affected_service_count"))
        .first()[0]
    )
    assert actual == expected > 0
    assert gold["agg_dispatch_priority"].count() == silver["work_order"].count()
    assert (
        gold["fact_network_telemetry_hourly"].agg(fn.sum("event_count")).first()[0]
        == silver["telemetry_event"].count()
    )
    assert gold["dim_date"].count() > 1


def test_deduplication_is_deterministic(bronze: dict[str, Any]) -> None:
    original = bronze["account"]
    stale = original.withColumn("ingestion_timestamp", fn.lit("2000-01-01T00:00:00Z")).withColumn(
        "account_name", fn.lit("stale")
    )
    result = conform_table(original.unionByName(stale), "account")
    assert result.count() == original.count()
    assert result.where("account_name = 'stale'").count() == 0


@pytest.mark.parametrize(
    "column,value",
    [("risk_score", "not-a-number"), ("risk_score", "2.0"), ("customer_id", "missing-customer")],
)
def test_silver_rejects_invalid_data(bronze: dict[str, Any], column: str, value: str) -> None:
    broken = dict(bronze)
    broken["churn_risk"] = broken["churn_risk"].withColumn(column, fn.lit(value))
    with pytest.raises(ValueError):
        build_silver(broken)


def test_silver_rejects_wrong_impact(silver: dict[str, Any]) -> None:
    broken = dict(silver)
    broken["bridge_incident_asset"] = broken["bridge_incident_asset"].where(
        "impact_role = 'root_cause'"
    )
    with pytest.raises(ValueError, match="Broken reference"):
        validate_silver(broken)


def test_investigation_totals_are_checked(silver: dict[str, Any]) -> None:
    broken = dict(silver)
    broken["investigation"] = broken["investigation"].withColumn(
        "related_case_count", fn.lit(999999)
    )
    with pytest.raises(ValueError, match="reconcile"):
        validate_evidence(broken)


def test_writes_require_explicit_replacement(spark: SparkSession) -> None:
    frame = spark.range(1)
    frame.createOrReplaceTempView("existing_medallion_output")
    with pytest.raises(ValueError, match="already exist"):
        write_layer(spark, {"existing_medallion_output": frame})
    spark.catalog.dropTempView("existing_medallion_output")


def test_default_generator_acceptance(tmp_path: Path) -> None:
    config = load_config(Path("src/data_generator/config/scenario_config.yaml"))
    datasets = build_datasets(config)
    for name, rows in datasets.items():
        write_csv(tmp_path / name, rows)
    assert run_validation(tmp_path) == 0


@pytest.mark.parametrize(
    "name", ["Transform_Nimbus_Bronze_To_Silver", "Transform_Nimbus_Silver_To_Gold"]
)
def test_notebook_artifacts(name: str) -> None:
    path = Path("notebooks") / f"{name}.ipynb"
    notebook = json.loads(path.read_text())
    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "synapse_pyspark"
    assert "parameters" in notebook["cells"][1]["metadata"]["tags"]
    for number, cell in enumerate(notebook["cells"], start=1):
        assert cell["metadata"]["language"] in {"markdown", "python"}
        assert all(line.endswith("\n") for line in cell["source"])
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
            compile("".join(cell["source"]), f"{path}:cell {number}", "exec")


def test_semantic_model_properties_are_merge_only() -> None:
    text = Path("semantic_model/tmdl/model.tmdl").read_text()
    assert text.strip().splitlines() == [
        "defaultPowerBIDataSourceVersion: powerBI_V3",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
    ]
    assert not re.search(r"(?m)^\s*(createOrReplace|ref|model|table|partition|expression)\b", text)
    guide = Path("docs/09-semantic-model-for-iq.md").read_text()
    assert "merge-only property fragment" in guide
    assert "A `ref` object cannot have properties" in guide
    assert "fresh full-model script" in guide


def test_semantic_measure_scripts_match_canonical_model() -> None:
    model = yaml.safe_load(Path("semantic_model/semantic_model.yml").read_text())
    text = Path("semantic_model/tmdl/measures.tmdl").read_text()
    assert text.startswith("createOrReplace")
    assert not re.search(r"(?m)^\s*//(?!/)|^\s*description:", text)
    declarations: dict[str, dict[str, str]] = {}
    table = ""
    current = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ref table "):
            table = stripped.removeprefix("ref table ").strip("'")
            assert table in model["tables"]
        elif stripped.startswith("measure "):
            name, separator, expression = stripped.removeprefix("measure ").partition(" =")
            assert separator
            current = name.strip("'")
            assert current not in declarations
            declarations[current] = {"table": table, "dax": expression.strip()}
        elif stripped.startswith(("VAR ", "RETURN ")):
            declarations[current]["dax"] += " " + stripped
        elif stripped.startswith("formatString:"):
            declarations[current]["format"] = stripped.partition(":")[2].strip()
    assert set(declarations) == set(model["measures"])
    for name, actual in declarations.items():
        expected = model["measures"][name]
        assert actual["table"] == expected["table"]
        assert re.sub(r"\s+", "", actual["dax"]) == re.sub(r"\s+", "", expected["dax"])
        assert actual["format"] == expected.get("format", "#,##0")
        for source_table, column in re.findall(r"'([^']+)'\[([^\]]+)\]", actual["dax"]):
            assert column in model["tables"][source_table]["columns"]


def test_semantic_relationship_scripts_match_model() -> None:
    model = yaml.safe_load(Path("semantic_model/semantic_model.yml").read_text())
    text = Path("semantic_model/tmdl/relationships.tmdl").read_text()
    assert text.startswith("createOrReplace")
    blocks = re.split(r"(?m)^[ \t]+relationship ", text)[1:]
    actual = {}
    for block in blocks:
        name = block.splitlines()[0]
        properties = dict(re.findall(r"(?m)^[ \t]+(\w+): (.+)$", block))
        actual[name] = properties
    assert len(actual) == len(model["relationships"])
    for relation in model["relationships"]:
        properties = actual[relation["name"].replace(" ", "_")]
        for side in ("from", "to"):
            source_table = relation[f"{side}_table"]
            column = relation[f"{side}_column"]
            assert column in model["tables"][source_table]["columns"]
            quoted = f"'{source_table}'" if " " in source_table else source_table
            assert properties[f"{side}Column"] == f"{quoted}.{column}"
        assert (properties.get("isActive", "true") == "true") == relation["active"]
        assert properties.get("crossFilteringBehavior", "oneDirection") == "oneDirection"


def test_semantic_active_filter_paths_are_unambiguous() -> None:
    model = yaml.safe_load(Path("semantic_model/semantic_model.yml").read_text())
    graph: dict[str, list[str]] = {table: [] for table in model["tables"]}
    for relation in model["relationships"]:
        if relation["active"]:
            graph[relation["to_table"]].append(relation["from_table"])
    for origin in graph:
        visits: dict[str, int] = {}
        pending = [(origin, {origin})]
        while pending:
            parent, path = pending.pop()
            for child in graph[parent]:
                assert child not in path, f"Active filter cycle from {origin}"
                visits[child] = visits.get(child, 0) + 1
                assert visits[child] == 1, f"Multiple active routes from {origin} to {child}"
                pending.append((child, path | {child}))


def test_step7_document_maps_every_base_table() -> None:
    model = yaml.safe_load(Path("semantic_model/semantic_model.yml").read_text())
    guide = Path("docs/09-semantic-model-for-iq.md").read_text()
    readme = Path("semantic_model/README.md").read_text()
    contracts = yaml.safe_load(Path("data_contracts/silver_gold_tables.yml").read_text())
    selected = set()
    for name, table in model["tables"].items():
        assert f"| `{table['source']}` | {name} |" in guide
        assert f"| `{table['source']}` | {name} |" in readme
        assert table["source"] in contracts["gold_tables"]
        selected.add(table["source"])
    optional = set(contracts["gold_tables"]) - selected
    assert len(model["tables"]) == 20
    assert optional == {
        "dim_region",
        "fact_network_telemetry_hourly",
        "agg_service_health_daily",
        "agg_customer_impact_by_incident",
    }
    assert all(f"`{name}`" in guide for name in optional)


def test_step7_validation_queries_reference_known_columns() -> None:
    model = yaml.safe_load(Path("semantic_model/semantic_model.yml").read_text())
    text = Path("semantic_model/validate_model.dax").read_text()
    assert len(re.findall(r"(?m)^EVALUATE", text)) == 3
    assert "INC-2026-ONT-001" in text
    assert "Dispatch Score Mismatches" in text
    assert "INFO.VIEW.RELATIONSHIPS()" in text
    for table, column in re.findall(r"'([^']+)'\[([^\]]+)\]", text):
        assert column in model["tables"][table]["columns"]
