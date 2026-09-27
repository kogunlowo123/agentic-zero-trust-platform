terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate-dev"
    storage_account_name = "stztplatformdev"
    container_name       = "tfstate"
    key                  = "zero-trust-platform/dev.tfstate"
  }
}
