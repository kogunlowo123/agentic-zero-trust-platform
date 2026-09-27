variable "location" {
  description = "Azure region for identity resources"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group for identity resources"
  type        = string
}

variable "aks_oidc_issuer_url" {
  description = "OIDC issuer URL from the AKS cluster — used to establish federated identity credentials"
  type        = string
}

variable "kubernetes_namespace" {
  description = "Kubernetes namespace where agent service accounts are created"
  type        = string
  default     = "agentic-zero-trust"
}

variable "azure_openai_resource_id" {
  description = "Full resource ID of the Azure OpenAI Cognitive Services account — e.g. /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<name>"
  type        = string
}

variable "key_vault_id" {
  description = "ID of the Key Vault where agent secrets are stored"
  type        = string
}

variable "servicebus_namespace_id" {
  description = "ID of the Service Bus namespace — each agent identity receives Data Sender and Data Receiver roles"
  type        = string
}

variable "search_service_id" {
  description = "ID of the Azure AI Search service — each agent identity receives Search Index Data Contributor role"
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
