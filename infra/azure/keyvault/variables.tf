variable "location" {
  description = "Azure region for Key Vault resources"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group for Key Vault resources"
  type        = string
}

variable "key_vault_name" {
  description = "Name of the Key Vault (must be globally unique, 3-24 alphanumeric chars and hyphens)"
  type        = string
}

variable "soft_delete_retention_days" {
  description = "Number of days to retain soft-deleted Key Vault resources"
  type        = number
  default     = 90
}

variable "aks_workload_identity_principal_id" {
  description = "Principal ID of the AKS workload identity — receives Key Vault Secrets User role"
  type        = string
}

variable "private_endpoints_subnet_id" {
  description = "ID of the subnet to deploy the private endpoint into"
  type        = string
}

variable "vnet_id" {
  description = "ID of the virtual network — used for the private DNS zone link"
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
