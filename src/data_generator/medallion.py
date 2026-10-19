"""Validated full-refresh transformations for the Nimbus Fabric demo."""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import Any

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as fn

__all__ = ["GOLD_SOURCES", "SPECS", "build_gold", "build_silver", "read_layer", "write_layer"]


@dataclass(frozen=True)
class TableSpec:
    keys: tuple[str, ...]
    columns: str


SPECS = {
    "account": TableSpec(
        ("account_id",),
        "account_id account_name account_type account_tier industry city province created_date",
    ),
    "customer": TableSpec(
        ("customer_id",),
        "customer_id account_id customer_name customer_type segment city province postal_code_prefix created_date",
    ),
    "product": TableSpec(
        ("product_id",), "product_id product_name service_type monthly_price product_family status"
    ),
    "subscription": TableSpec(
        ("subscription_id",),
        "subscription_id account_id product_id service_type start_date status monthly_recurring_revenue",
    ),
    "device": TableSpec(
        ("device_id",),
        "device_id subscription_id device_type model firmware_version activation_date device_status",
    ),
    "service_instance": TableSpec(
        ("service_instance_id",),
        "service_instance_id subscription_id device_id network_asset_id service_type access_type activation_date status",
    ),
    "network_asset": TableSpec(
        ("network_asset_id",),
        "network_asset_id parent_asset_id asset_type asset_name region city latitude longitude vendor technology operational_status",
    ),
    "telemetry_event": TableSpec(
        ("telemetry_event_id",),
        "telemetry_event_id network_asset_id event_time metric_name metric_value metric_unit severity_band scenario_id",
    ),
    "alarm": TableSpec(
        ("alarm_id",),
        "alarm_id telemetry_event_id network_asset_id incident_id alarm_type severity status raised_time cleared_time",
    ),
    "incident": TableSpec(
        ("incident_id",),
        "incident_id network_asset_id scenario_id incident_type root_cause severity status start_time detected_time resolution_time region affected_service_type",
    ),
    "support_case": TableSpec(
        ("case_id",),
        "case_id customer_id account_id service_instance_id incident_id opened_time closed_time channel case_reason sentiment_score case_status customer_tier scenario_id",
    ),
    "technician": TableSpec(
        ("technician_id",),
        "technician_id technician_name home_region skill_set shift availability_status",
    ),
    "work_order": TableSpec(
        ("work_order_id",),
        "work_order_id incident_id network_asset_id technician_id priority status created_time scheduled_time completed_time",
    ),
    "sla_exposure": TableSpec(
        ("exposure_id",),
        "exposure_id incident_id account_id customer_tier breach_type exposure_amount currency exposure_status",
    ),
    "churn_risk": TableSpec(
        ("risk_id",),
        "risk_id customer_id risk_score risk_band primary_driver repeat_case_count model_version scored_time",
    ),
    "bridge_incident_asset": TableSpec(
        ("incident_id", "network_asset_id"), "incident_id network_asset_id impact_role"
    ),
    "bridge_incident_service": TableSpec(
        ("incident_id", "service_instance_id"), "incident_id service_instance_id"
    ),
    "investigation": TableSpec(
        ("investigation_id",),
        "investigation_id incident_id title summary affected_asset_count affected_service_count related_case_count sla_exposure_amount status created_time created_by",
    ),
}

BRONZE_NAMES = {
    "account": "raw_accounts",
    "customer": "raw_customers",
    "product": "raw_products",
    "subscription": "raw_subscriptions",
    "device": "raw_devices",
    "service_instance": "raw_service_instances",
    "network_asset": "raw_network_assets",
    "telemetry_event": "raw_telemetry_events",
    "alarm": "raw_alarms",
    "incident": "raw_incidents",
    "support_case": "raw_support_cases",
    "technician": "raw_technicians",
    "work_order": "raw_work_orders",
    "sla_exposure": "raw_sla_exposure",
    "churn_risk": "raw_churn_risk",
    "bridge_incident_asset": "raw_bridge_incident_asset",
    "bridge_incident_service": "raw_bridge_incident_service",
    "investigation": "raw_investigations",
}

GOLD_SOURCES = {
    "dim_account": "account",
    "dim_customer": "customer",
    "dim_product": "product",
    "dim_device": "device",
    "dim_service_instance": "service_instance",
    "dim_network_asset": "network_asset",
    "dim_technician": "technician",
    "bridge_subscription": "subscription",
    "fact_network_telemetry": "telemetry_event",
    "fact_alarm": "alarm",
    "fact_incident": "incident",
    "fact_support_case": "support_case",
    "fact_work_order": "work_order",
    "fact_sla_exposure": "sla_exposure",
    "fact_churn_risk": "churn_risk",
    "fact_investigation": "investigation",
    "bridge_incident_asset": "bridge_incident_asset",
    "bridge_incident_service": "bridge_incident_service",
}

FOREIGN_KEYS = (
    ("customer", "account_id", "account", False),
    ("subscription", "account_id", "account", False),
    ("subscription", "product_id", "product", False),
    ("device", "subscription_id", "subscription", False),
    ("service_instance", "subscription_id", "subscription", False),
    ("service_instance", "device_id", "device", False),
    ("service_instance", "network_asset_id", "network_asset", False),
    ("network_asset", "parent_asset_id", "network_asset", True),
    ("telemetry_event", "network_asset_id", "network_asset", False),
    ("incident", "network_asset_id", "network_asset", False),
    ("alarm", "telemetry_event_id", "telemetry_event", False),
    ("alarm", "network_asset_id", "network_asset", False),
    ("alarm", "incident_id", "incident", True),
    ("support_case", "customer_id", "customer", False),
    ("support_case", "account_id", "account", False),
    ("support_case", "service_instance_id", "service_instance", False),
    ("support_case", "incident_id", "incident", True),
    ("work_order", "incident_id", "incident", False),
    ("work_order", "network_asset_id", "network_asset", False),
    ("work_order", "technician_id", "technician", True),
    ("sla_exposure", "incident_id", "incident", False),
    ("sla_exposure", "account_id", "account", False),
    ("churn_risk", "customer_id", "customer", False),
    ("bridge_incident_asset", "incident_id", "incident", False),
    ("bridge_incident_asset", "network_asset_id", "network_asset", False),
    ("bridge_incident_service", "incident_id", "incident", False),
    ("bridge_incident_service", "service_instance_id", "service_instance", False),
    ("investigation", "incident_id", "incident", False),
)


def reject_rows(frame: DataFrame, condition: Column, label: str) -> None:
    if frame.where(condition).limit(1).count():
        raise ValueError(label)


def require_reference(
    child: DataFrame,
    parent: DataFrame,
    keys: list[str],
    label: str,
    nullable: bool = False,
) -> None:
    selected = child.select(*keys)
    if nullable:
        selected = selected.dropna(subset=keys)
    if selected.join(parent.select(*keys).distinct(), keys, "left_anti").limit(1).count():
        raise ValueError(f"Broken reference: {label}")


def column_type(name: str) -> str:
    if name.endswith("_time") or name == "ingestion_timestamp":
        return "timestamp"
    if name.endswith("_date"):
        return "date"
    if name in {
        "monthly_price",
        "monthly_recurring_revenue",
        "exposure_amount",
        "sla_exposure_amount",
    }:
        return "decimal(18,2)"
    if name in {"latitude", "longitude", "metric_value", "sentiment_score", "risk_score"}:
        return "double"
    if name in {
        "repeat_case_count",
        "affected_asset_count",
        "affected_service_count",
        "related_case_count",
    }:
        return "long"
    return "string"


def conform_table(frame: DataFrame, name: str) -> DataFrame:
    spec = SPECS[name]
    missing = set(spec.columns.split()) - set(frame.columns)
    if missing:
        raise ValueError(f"{name}: missing columns {sorted(missing)}")
    normalized = [fn.trim(fn.col(column).cast("string")).alias(column) for column in frame.columns]
    frame = frame.select(*normalized)
    frame = frame.select(
        *[fn.when(fn.col(column) != "", fn.col(column)).alias(column) for column in frame.columns]
    )
    invalid = [fn.col(key).isNull() for key in spec.keys]
    converted_columns = []
    for column in frame.columns:
        target_type = column_type(column)
        converted = fn.col(column)
        if target_type != "string":
            converted = fn.expr(f"try_cast(`{column}` as {target_type})")
            invalid.append(fn.col(column).isNotNull() & converted.isNull())
        converted_columns.append(converted.alias(column))
    reject_rows(
        frame,
        reduce(lambda left, right: left | right, invalid),
        f"{name}: null business key or invalid typed value",
    )
    frame = frame.select(*converted_columns)
    tie_breaker = fn.sha2(
        fn.to_json(fn.struct(*[fn.col(col) for col in sorted(frame.columns)])), 256
    )
    ordering = (
        [fn.col("ingestion_timestamp").desc_nulls_last()]
        if "ingestion_timestamp" in frame.columns
        else []
    )
    window = Window.partitionBy(*spec.keys).orderBy(*ordering, tie_breaker)
    return (
        frame.withColumn("_row_number", fn.row_number().over(window))
        .where("_row_number = 1")
        .drop("_row_number")
    )


def build_silver(bronze: dict[str, DataFrame]) -> dict[str, DataFrame]:
    missing = set(SPECS) - set(bronze)
    if missing:
        raise ValueError(f"Missing Bronze inputs: {sorted(missing)}")
    silver = {name: conform_table(bronze[name], name).cache() for name in SPECS}
    try:
        validate_silver(silver)
    except Exception:
        for frame in silver.values():
            frame.unpersist()
        raise
    return silver


def validate_silver(tables: dict[str, DataFrame]) -> None:
    for child, key, parent, nullable in FOREIGN_KEYS:
        parent_key = SPECS[parent].keys[0]
        parent_frame = tables[parent].select(fn.col(parent_key).alias(key))
        require_reference(tables[child], parent_frame, [key], f"{child}.{key}", nullable)
    required_times = {
        "telemetry_event": ("event_time",),
        "incident": ("start_time", "detected_time"),
        "alarm": ("raised_time",),
        "support_case": ("opened_time",),
        "work_order": ("created_time", "scheduled_time"),
        "churn_risk": ("scored_time",),
        "investigation": ("created_time",),
    }
    for name, columns in required_times.items():
        for column in columns:
            reject_rows(
                tables[name], fn.col(column).isNull(), f"{name}.{column}: required timestamp"
            )
    timelines = {
        "incident": (("start_time", "detected_time"), ("detected_time", "resolution_time")),
        "alarm": (("raised_time", "cleared_time"),),
        "support_case": (("opened_time", "closed_time"),),
        "work_order": (("created_time", "scheduled_time"), ("scheduled_time", "completed_time")),
    }
    for name, pairs in timelines.items():
        for earlier, later in pairs:
            reject_rows(
                tables[name], fn.col(later) < fn.col(earlier), f"{name}: {later} precedes {earlier}"
            )
    for name, column, lower, upper in (
        ("churn_risk", "risk_score", 0, 1),
        ("support_case", "sentiment_score", -1, 1),
        ("network_asset", "latitude", -90, 90),
        ("network_asset", "longitude", -180, 180),
    ):
        reject_rows(
            tables[name],
            fn.col(column).isNull() | fn.isnan(column) | ~fn.col(column).between(lower, upper),
            f"{name}.{column}: outside range",
        )
    reject_rows(
        tables["telemetry_event"],
        fn.col("metric_value").isNull()
        | fn.isnan("metric_value")
        | fn.col("metric_value").isin(float("inf"), float("-inf")),
        "telemetry_event.metric_value: invalid measurement",
    )
    for name, column in (
        ("product", "monthly_price"),
        ("subscription", "monthly_recurring_revenue"),
        ("sla_exposure", "exposure_amount"),
        ("investigation", "sla_exposure_amount"),
    ):
        reject_rows(
            tables[name],
            fn.col(column).isNull() | (fn.col(column) < 0),
            f"{name}.{column}: invalid amount",
        )
    service = tables["service_instance"]
    subscriptions = tables["subscription"]
    assets = tables["bridge_incident_asset"]
    impact = tables["bridge_incident_service"]
    affected = impact.join(service, "service_instance_id").join(
        tables["incident"].select("incident_id", "affected_service_type"), "incident_id"
    )
    require_reference(
        affected, assets, ["incident_id", "network_asset_id"], "impacted service/asset"
    )
    reject_rows(
        affected,
        fn.col("service_type") != fn.col("affected_service_type"),
        "Impacted service has wrong service type",
    )
    require_reference(
        tables["incident"], assets, ["incident_id", "network_asset_id"], "incident root asset"
    )
    require_reference(
        tables["support_case"].where("incident_id IS NOT NULL"),
        impact,
        ["incident_id", "service_instance_id"],
        "support case/impact",
    )
    require_reference(
        tables["alarm"].where("incident_id IS NOT NULL"),
        assets,
        ["incident_id", "network_asset_id"],
        "alarm/impact",
    )
    require_reference(
        tables["work_order"], assets, ["incident_id", "network_asset_id"], "work order/impact"
    )
    owned_services = service.join(
        subscriptions.select("subscription_id", "account_id"), "subscription_id"
    )
    require_reference(
        tables["support_case"],
        owned_services,
        ["service_instance_id", "account_id"],
        "support case/service owner",
    )
    require_reference(
        tables["support_case"],
        tables["customer"],
        ["customer_id", "account_id"],
        "support case/customer owner",
    )
    require_reference(
        service, tables["device"], ["device_id", "subscription_id"], "service/device subscription"
    )
    affected_accounts = (
        impact.join(owned_services, "service_instance_id")
        .select("incident_id", "account_id")
        .distinct()
    )
    require_reference(
        tables["sla_exposure"],
        affected_accounts,
        ["incident_id", "account_id"],
        "SLA exposure/impacted account",
    )
    work = tables["work_order"].join(
        tables["incident"].select("incident_id", "start_time", "resolution_time"), "incident_id"
    )
    reject_rows(
        work,
        (fn.col("created_time") < fn.col("start_time"))
        | (
            (fn.col("status") == "Completed")
            & (fn.col("completed_time") > fn.col("resolution_time"))
        ),
        "Work order outside incident timeline",
    )
    validate_evidence(tables)


def incident_totals(tables: dict[str, DataFrame]) -> DataFrame:
    totals = tables["incident"].select("incident_id")
    for name, metric, key in (
        ("bridge_incident_asset", "affected_asset_count", "network_asset_id"),
        ("bridge_incident_service", "affected_service_count", "service_instance_id"),
        ("support_case", "related_case_count", "case_id"),
    ):
        totals = totals.join(
            tables[name].groupBy("incident_id").agg(fn.countDistinct(key).alias(metric)),
            "incident_id",
            "left",
        )
    totals = totals.join(
        tables["sla_exposure"]
        .groupBy("incident_id")
        .agg(fn.sum("exposure_amount").alias("sla_exposure_amount")),
        "incident_id",
        "left",
    )
    return totals.fillna(0)


def validate_evidence(tables: dict[str, DataFrame]) -> None:
    evidence = tables["investigation"]
    reject_rows(
        evidence.groupBy("incident_id").count(),
        fn.col("count") > 1,
        "Multiple investigations per incident",
    )
    require_reference(
        tables["incident"].where("severity = 'High'"),
        evidence,
        ["incident_id"],
        "High severity incident/investigation",
    )
    metrics = (
        "affected_asset_count",
        "affected_service_count",
        "related_case_count",
        "sla_exposure_amount",
    )
    expected = incident_totals(tables).select(
        "incident_id", *[fn.col(metric).alias(f"expected_{metric}") for metric in metrics]
    )
    joined = evidence.join(expected, "incident_id")
    reject_rows(
        joined,
        reduce(
            lambda left, right: left | right,
            (~fn.col(metric).eqNullSafe(fn.col(f"expected_{metric}")) for metric in metrics),
        ),
        "Investigation counts or SLA amount do not reconcile to source tables",
    )


def read_layer(
    spark: SparkSession, notebookutils: Any, root: str, layer: str, schema: str = "auto"
) -> dict[str, DataFrame]:
    if layer not in {"bronze", "silver"}:
        raise ValueError("Source layer must be bronze or silver")
    names = BRONZE_NAMES if layer == "bronze" else {name: name for name in SPECS}
    first_table = next(iter(names.values()))
    if schema == "auto":
        candidates = [f"{root}/Tables/{first_table}", f"{root}/Tables/dbo/{first_table}"]
        found = [path for path in candidates if notebookutils.fs.exists(f"{path}/_delta_log")]
        if len(found) != 1:
            raise ValueError(
                f"Cannot locate {first_table}: expected exactly one legacy or dbo Delta table. Set source_schema explicitly for custom schemas."
            )
        table_root = found[0].rsplit("/", 1)[0]
    else:
        table_root = f"{root}/Tables" + (f"/{schema}" if schema else "")
    return {
        name: spark.read.format("delta").load(f"{table_root}/{table}")
        for name, table in names.items()
    }


def write_layer(
    spark: SparkSession, tables: dict[str, DataFrame], allow_replace: bool = False
) -> dict[str, int]:
    existing = [name for name in tables if spark.catalog.tableExists(name)]
    if existing and not allow_replace:
        raise ValueError(
            f"Output tables already exist: {existing}. Review the target lakehouse and explicitly set allow_replace = True for a full refresh."
        )
    counts = {name: frame.count() for name, frame in tables.items()}
    for name, frame in tables.items():
        frame.write.format("delta").mode(
            "overwrite" if allow_replace else "errorifexists"
        ).saveAsTable(name)
        stored = spark.table(name)
        stored_types = [(field.name, field.dataType) for field in stored.schema]
        expected_types = [(field.name, field.dataType) for field in frame.schema]
        if stored.count() != counts[name] or stored_types != expected_types:
            raise ValueError(f"Delta readback mismatch: {name}")
        print(f"PASS: {name}: {counts[name]} rows")
    return counts


def build_gold(silver: dict[str, DataFrame]) -> dict[str, DataFrame]:
    validate_silver(silver)
    gold = {target: silver[source] for target, source in GOLD_SOURCES.items()}
    gold["fact_incident"] = gold["fact_incident"].withColumn("start_date", fn.to_date("start_time"))
    gold["fact_support_case"] = gold["fact_support_case"].withColumn(
        "opened_date", fn.to_date("opened_time")
    )
    gold["fact_work_order"] = gold["fact_work_order"].withColumn(
        "created_date", fn.to_date("created_time")
    )
    telemetry = silver["telemetry_event"]
    hourly = telemetry.withColumn("event_hour", fn.date_trunc("hour", "event_time"))
    gold["fact_network_telemetry_hourly"] = hourly.groupBy(
        "network_asset_id", "metric_name", "metric_unit", "event_hour"
    ).agg(
        fn.count("*").alias("event_count"),
        fn.avg("metric_value").alias("avg_metric_value"),
        fn.min("metric_value").alias("min_metric_value"),
        fn.max("metric_value").alias("max_metric_value"),
        fn.sum(fn.when(fn.col("severity_band") == "Critical", 1).otherwise(0)).alias(
            "critical_event_count"
        ),
    )
    daily = telemetry.withColumn("event_date", fn.to_date("event_time"))
    service_counts = (
        silver["service_instance"]
        .groupBy("network_asset_id")
        .agg(fn.countDistinct("service_instance_id").alias("served_service_count"))
    )
    gold["agg_service_health_daily"] = (
        daily.groupBy("network_asset_id", "metric_name", "metric_unit", "event_date")
        .agg(
            fn.count("*").alias("event_count"),
            fn.avg("metric_value").alias("avg_metric_value"),
            fn.sum(fn.when(fn.col("severity_band") == "Critical", 1).otherwise(0)).alias(
                "critical_event_count"
            ),
        )
        .join(service_counts, "network_asset_id", "left")
        .fillna(0, ["served_service_count"])
    )
    gold["dim_region"] = silver["network_asset"].select("region").distinct()
    date_frames = [
        frame.select(fn.to_date(column).alias("date"))
        for frame in silver.values()
        for column in frame.columns
        if column_type(column) in {"date", "timestamp"}
    ]
    dates = reduce(lambda left, right: left.unionByName(right), date_frames).dropna()
    bounds = dates.agg(fn.min("date").alias("first_date"), fn.max("date").alias("last_date"))
    calendar = bounds.select(fn.explode(fn.sequence("first_date", "last_date")).alias("date"))
    gold["dim_date"] = calendar.select(
        "date",
        fn.year("date").alias("year"),
        fn.month("date").alias("month"),
        fn.date_format("date", "MMMM").alias("month_name"),
        fn.to_date(fn.date_trunc("week", fn.col("date").cast("timestamp"))).alias(
            "week_start_date"
        ),
        fn.date_format("date", "EEEE").alias("day_name"),
    )
    impact_accounts = (
        silver["bridge_incident_service"]
        .join(
            silver["service_instance"].select("service_instance_id", "subscription_id"),
            "service_instance_id",
        )
        .join(silver["subscription"].select("subscription_id", "account_id"), "subscription_id")
    )
    segments = silver["account"].select(
        "account_id",
        fn.when(fn.col("account_type") == "Consumer", "Residential")
        .otherwise(fn.col("account_type"))
        .alias("segment"),
    )
    impacted = impact_accounts.join(segments, "account_id")
    account_pairs = impacted.select("incident_id", "account_id", "segment").distinct()
    services = impacted.groupBy("incident_id", "segment").agg(
        fn.countDistinct("service_instance_id").alias("affected_service_count"),
        fn.countDistinct("account_id").alias("affected_account_count"),
    )
    customers = (
        account_pairs.join(silver["customer"].select("account_id", "customer_id"), "account_id")
        .groupBy("incident_id", "segment")
        .agg(fn.countDistinct("customer_id").alias("affected_customer_count"))
    )
    cases = (
        silver["support_case"]
        .join(segments, "account_id")
        .groupBy("incident_id", "segment")
        .agg(fn.countDistinct("case_id").alias("related_case_count"))
    )
    exposure = (
        silver["sla_exposure"]
        .join(segments, "account_id")
        .groupBy("incident_id", "segment")
        .agg(fn.sum("exposure_amount").alias("sla_exposure_amount"))
    )
    impact_summary = (
        services.join(customers, ["incident_id", "segment"], "left")
        .join(cases, ["incident_id", "segment"], "left")
        .join(exposure, ["incident_id", "segment"], "left")
        .fillna(0)
    )
    gold["agg_customer_impact_by_incident"] = impact_summary
    expected = incident_totals(silver)
    summary_totals = impact_summary.groupBy("incident_id").agg(
        fn.sum("affected_service_count").alias("actual_services"),
        fn.sum("related_case_count").alias("actual_cases"),
        fn.sum("sla_exposure_amount").alias("actual_exposure"),
    )
    reconciled = expected.join(summary_totals, "incident_id", "left").fillna(0)
    reject_rows(
        reconciled,
        (fn.col("affected_service_count") != fn.col("actual_services"))
        | (fn.col("related_case_count") != fn.col("actual_cases"))
        | (fn.col("sla_exposure_amount") != fn.col("actual_exposure")),
        "Gold incident impact totals do not reconcile to Silver",
    )
    tiers = (
        account_pairs.join(silver["account"].select("account_id", "account_tier"), "account_id")
        .groupBy("incident_id")
        .agg(
            fn.max(
                fn.when(fn.col("account_tier") == "Enterprise", 10)
                .when(fn.col("account_tier") == "Premium", 5)
                .otherwise(0)
            ).alias("customer_tier_weight")
        )
    )
    dispatch = (
        silver["work_order"]
        .join(silver["incident"].select("incident_id", "severity"), "incident_id")
        .join(expected, "incident_id")
        .join(tiers, "incident_id", "left")
        .fillna(0, ["customer_tier_weight"])
    )
    dispatch = (
        dispatch.withColumn(
            "severity_weight",
            fn.when(fn.col("severity") == "High", 40)
            .when(fn.col("severity") == "Medium", 20)
            .otherwise(10),
        )
        .withColumn(
            "affected_subscriber_weight",
            fn.least(fn.lit(25.0), fn.col("affected_service_count") / 20.0),
        )
        .withColumn(
            "sla_exposure_weight",
            fn.least(fn.lit(25.0), fn.col("sla_exposure_amount").cast("double") / 1000.0),
        )
    )
    gold["agg_dispatch_priority"] = dispatch.withColumn(
        "dispatch_priority_score",
        fn.col("severity_weight")
        + fn.col("affected_subscriber_weight")
        + fn.col("sla_exposure_weight")
        + fn.col("customer_tier_weight"),
    )
    return gold
