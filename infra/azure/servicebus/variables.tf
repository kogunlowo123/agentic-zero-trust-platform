variable "location" {
  description = "Azure region for Service Bus resources"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group for Service Bus resources"
  type        = string
}

variable "namespace_name" {
  description = "Name of the Service Bus namespace (must be globally unique)"
  type        = string
}

variable "aks_identity_principal_id" {
  description = "Principal ID of the AKS kubelet identity — receives Service Bus Data Sender and Receiver roles"
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
