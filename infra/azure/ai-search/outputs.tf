output "search_service_id" {
  description = "ID of the Azure AI Search service"
  value       = azurerm_search_service.main.id
}

output "search_service_name" {
  description = "Name of the Azure AI Search service"
  value       = azurerm_search_service.main.name
}

output "search_service_endpoint" {
  description = "HTTPS endpoint for the Azure AI Search service"
  value       = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "primary_key" {
  description = "Primary admin API key for the search service (sensitive; use only for initial bootstrap — prefer Entra-based auth)"
  value       = azurerm_search_service.main.primary_key
  sensitive   = true
}

output "resource_group_name" {
  description = "Name of the AI Search resource group"
  value       = azurerm_resource_group.ai_search.name
}
