variable "location" {
  description = "Azure region for PostgreSQL resources"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group for PostgreSQL resources"
  type        = string
}

variable "server_name" {
  description = "Name of the PostgreSQL Flexible Server"
  type        = string
}

variable "sku_name" {
  description = "SKU name for the PostgreSQL Flexible Server"
  type        = string
  default     = "GP_Standard_D4s_v3"
}

variable "postgres_version" {
  description = "PostgreSQL major version"
  type        = string
  default     = "16"
}

variable "delegated_subnet_id" {
  description = "ID of the subnet delegated to Microsoft.DBforPostgreSQL/flexibleServers"
  type        = string
}

variable "private_dns_zone_id" {
  description = "ID of the private DNS zone for PostgreSQL (privatelink.postgres.database.azure.com)"
  type        = string
}

variable "database_name" {
  description = "Name of the initial platform database"
  type        = string
  default     = "platform"
}

variable "aks_workload_identity_object_id" {
  description = "Object ID of the AKS workload identity to register as PostgreSQL AAD administrator"
  type        = string
}

variable "aks_workload_identity_principal_name" {
  description = "Display name of the AKS workload identity (used as the PostgreSQL AAD administrator principal name)"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
