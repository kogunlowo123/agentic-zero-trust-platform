terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

resource "azurerm_resource_group" "servicebus" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_servicebus_namespace" "main" {
  name                          = var.namespace_name
  location                      = azurerm_resource_group.servicebus.location
  resource_group_name           = azurerm_resource_group.servicebus.name
  sku                           = "Premium"
  capacity                      = 1
  local_auth_enabled            = false
  public_network_access_enabled = false
  minimum_tls_version           = "1.2"

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_servicebus_queue" "policy_violations" {
  name         = "policy-violations"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_size_in_megabytes                = 5120
  lock_duration                        = "PT5M"
  requires_duplicate_detection         = true
  duplicate_detection_history_time_window = "PT10M"
  dead_lettering_on_message_expiration = true
  max_delivery_count                   = 10
  default_message_ttl                  = "P14D"
  enable_partitioning                  = false
}

resource "azurerm_servicebus_queue" "access_requests" {
  name         = "access-requests"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_size_in_megabytes                = 5120
  lock_duration                        = "PT5M"
  requires_duplicate_detection         = true
  duplicate_detection_history_time_window = "PT10M"
  dead_lettering_on_message_expiration = true
  max_delivery_count                   = 10
  default_message_ttl                  = "P14D"
  enable_partitioning                  = false
}

resource "azurerm_servicebus_queue" "posture_events" {
  name         = "posture-events"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_size_in_megabytes                = 5120
  lock_duration                        = "PT5M"
  requires_duplicate_detection         = true
  duplicate_detection_history_time_window = "PT10M"
  dead_lettering_on_message_expiration = true
  max_delivery_count                   = 10
  default_message_ttl                  = "P14D"
  enable_partitioning                  = false
}

resource "azurerm_private_dns_zone" "servicebus" {
  name                = "privatelink.servicebus.windows.net"
  resource_group_name = azurerm_resource_group.servicebus.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "servicebus" {
  name                  = "pdnsl-sb-${var.environment}"
  resource_group_name   = azurerm_resource_group.servicebus.name
  private_dns_zone_name = azurerm_private_dns_zone.servicebus.name
  virtual_network_id    = var.vnet_id
  registration_enabled  = false
  tags                  = var.tags
}

resource "azurerm_private_endpoint" "servicebus" {
  name                = "pe-sb-${var.environment}"
  location            = azurerm_resource_group.servicebus.location
  resource_group_name = azurerm_resource_group.servicebus.name
  subnet_id           = var.private_endpoints_subnet_id

  private_service_connection {
    name                           = "psc-sb-${var.environment}"
    private_connection_resource_id = azurerm_servicebus_namespace.main.id
    subresource_names              = ["namespace"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdnszg-sb"
    private_dns_zone_ids = [azurerm_private_dns_zone.servicebus.id]
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "servicebus_data_sender" {
  scope                = azurerm_servicebus_namespace.main.id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = var.aks_identity_principal_id
}

resource "azurerm_role_assignment" "servicebus_data_receiver" {
  scope                = azurerm_servicebus_namespace.main.id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = var.aks_identity_principal_id
}
