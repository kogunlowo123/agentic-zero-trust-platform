terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate-prod"
    storage_account_name = "stztplatformprod"
    container_name       = "tfstate"
    key                  = "zero-trust-platform/prod.tfstate"
  }
}
