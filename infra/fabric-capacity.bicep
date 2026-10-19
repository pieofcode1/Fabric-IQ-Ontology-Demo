targetScope = 'resourceGroup'

@description('Lowercase alphanumeric Fabric capacity name, starting with a letter.')
@minLength(3)
@maxLength(63)
param capacityName string

@description('Approved Azure region with Fabric workload availability and CU quota.')
param location string

@description('Budget-approved Fabric SKU. No default to avoid an accidental sizing choice.')
param skuName string

@description('Internal tenant user principal name for the capacity administrator.')
param administratorUpn string

@description('Owner responsible for demo cost and lifecycle.')
param owner string

resource capacity 'Microsoft.Fabric/capacities@2026-08-01-preview' = {
  name: capacityName
  location: location
  sku: {
    name: skuName
    tier: 'Fabric'
  }
  properties: {
    administration: {
      members: [administratorUpn]
    }
    overage: {
      state: 'Disabled'
    }
  }
  tags: {
    environment: 'demo'
    project: 'nimbus-fabric-iq'
    owner: owner
  }
}

output capacityArmId string = capacity.id
