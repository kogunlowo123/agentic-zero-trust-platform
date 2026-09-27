variable "location" {
  description = "Azure region for AI Search resources"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group for AI Search resources"
  type        = string
}

variable "search_service_name" {
  description = "Name of the Azure AI Search service (must be globally unique)"
  type        = string
}

variable "replica_count" {
  description = "Number of replicas for the search service (minimum 2 for HA)"
  type        = number
  default     = 2
}

variable "aks_identity_principal_id" {
  description = "Principal ID of the AKS kubelet identity — receives Search Index Data Contributor role"
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
