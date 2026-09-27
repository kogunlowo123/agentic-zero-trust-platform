terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

resource "azurerm_resource_group" "ai_search" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_search_service" "main" {
  name                          = var.search_service_name
  resource_group_name           = azurerm_resource_group.ai_search.name
  location                      = azurerm_resource_group.ai_search.location
  sku                           = "standard"
  replica_count                 = var.replica_count
  partition_count               = 1
  public_network_access_enabled = false
  local_authentication_enabled  = false
  hosting_mode                  = "default"
  semantic_search_sku           = "free"

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_private_dns_zone" "search" {
  name                = "privatelink.search.windows.net"
  resource_group_name = azurerm_resource_group.ai_search.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "search" {
  name                  = "pdnsl-search-${var.environment}"
  resource_group_name   = azurerm_resource_group.ai_search.name
  private_dns_zone_name = azurerm_private_dns_zone.search.name
  virtual_network_id    = var.vnet_id
  registration_enabled  = false
  tags                  = var.tags
}

resource "azurerm_private_endpoint" "search" {
  name                = "pe-search-${var.environment}"
  location            = azurerm_resource_group.ai_search.location
  resource_group_name = azurerm_resource_group.ai_search.name
  subnet_id           = var.private_endpoints_subnet_id

  private_service_connection {
    name                           = "psc-search-${var.environment}"
    private_connection_resource_id = azurerm_search_service.main.id
    subresource_names              = ["searchService"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdnszg-search"
    private_dns_zone_ids = [azurerm_private_dns_zone.search.id]
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "search_index_data_contributor" {
  scope                = azurerm_search_service.main.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = var.aks_identity_principal_id
}
