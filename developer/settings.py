import pulumi
from pulumi_aws import config

"""
Configuration variables from pulumi settings file
"""
stack_config = pulumi.Config()
stack_name = pulumi.get_stack()
logged_in_person = stack_config.get("loggedInPerson")

"""
General cost tags populated to every single resource in the account:
"""
general_tags = {
    "stack:name": "themountain_developer",
    "stack:pulumi": f"{stack_name}",
    "owner": f"{logged_in_person}"
}

"""
Misc variables
"""
mtn_vpc_cidr = "10.200.0.0/16"

mtn_public_subnet_cidrs = [
    "10.200.0.0/20",
    "10.200.16.0/20"
]
mtn_private_subnet_cidrs = [
    "10.200.32.0/20",
    "10.200.48.0/20"
]
mtn_eks_cp_subnet_cidrs = [
    "10.200.64.0/24",
    "10.200.65.0/24"
]

deployment_region = config.region
endpoint_services = ["ecr.api","ecr.dkr","ec2","sts","logs","s3","email-smtp","cloudformation"]
cluster_descriptor = "mtn_developer"

"""
Flux Bootstrap args
"""
flux_github_repo_owner = stack_config.require("flux-github-repo-owner")
flux_github_repo_name = stack_config.require("flux-github-repo-name")
flux_cli_version = "0.37.0"
flux_github_token = stack_config.require_secret("flux-github-token")