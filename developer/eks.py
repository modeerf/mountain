from pulumi_awsx import iam, ec2, eks, config, cloudwatch
import pulumi_eks as eks_provider
from pulumi import export, ResourceOptions
import pulumi_kubernetes as k8s

from settings import general_tags, cluster_descriptor
from vpc import mtn_vpc, mtn_private_subnets, mtn_eks_cp_subnets
from helpers import create_iam_role, create_oidc_role, create_policy

"""
Shared EKS resources
"""

# Create an EKS cluster role
eks_iam_role_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
]

eks_iam_role = create_iam_role(f"{cluster_descriptor}-eks-role", "Service", "eks.amazonaws.com", eks_iam_role_policy_arns)

# Create a default node role for Karpenter
karpenter_default_nodegroup_role_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
]

# Create a default Fargate execution role:
default_fargate_pod_execution_role_policy = [
    "arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy"
]

# VPC CNI service account policies:
cni_service_account_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
]

# Create a default mtn EKS cluster nodegroup security group:
mtn_nodegroup_security_group = ec2.SecurityGroup(f"custom-node-attach-{cluster_descriptor}",
    description=f"{cluster_descriptor} custom node security group",
    vpc_id=mtn_vpc.id,
    tags={**general_tags, "Name": f"custom-node-attach-{cluster_descriptor}", "karpenter.sh/discovery": f"{cluster_descriptor}"}
)

mtn_nodegroup_security_group_inbound_custom_cidrs = ec2.SecurityGroupRule(f"inbound-eks-node-{cluster_descriptor}",
    type="ingress",
    from_port=443,
    to_port=443,
    protocol="tcp",
    cidr_blocks=["0.0.0.0/0"],
    security_group_id=mtn_nodegroup_security_group.id
)

mtn_nodegroup_security_group_oubound_custom_cidrs = ec2.SecurityGroupRule(f"outbound-eks-node-{cluster_descriptor}",
    type="egress",
    to_port=0,
    protocol="-1",
    from_port=0,
    cidr_blocks=["0.0.0.0/0"],
    security_group_id=mtn_nodegroup_security_group.id
)

# Create a default mtn EKS cluster security group:
mtn_cluster_security_group = ec2.SecurityGroup(f"custom-cluster-attach-{cluster_descriptor}",
    description=f"{cluster_descriptor} custom security group",
    vpc_id=mtn_vpc.id,
    tags={**general_tags, "Name": f"custom-cluster-attach-{cluster_descriptor}"}
)

mtn_cluster_security_group_inbound_custom_cidrs = ec2.SecurityGroupRule(f"inbound-eks-cp-{cluster_descriptor}",
    type="ingress",
    from_port=443,
    to_port=443,
    protocol="tcp",
    cidr_blocks=["0.0.0.0/0"],
    security_group_id=mtn_cluster_security_group.id
)

mtn_cluster_security_group_oubound_custom_cidrs = ec2.SecurityGroupRule(f"outbound-eks-cp-{cluster_descriptor}",
    type="egress",
    to_port=0,
    protocol="-1",
    from_port=0,
    cidr_blocks=["0.0.0.0/0"],
    security_group_id=mtn_cluster_security_group.id
)

# Create a default Karpenter node role and instance profile:
karpenter_node_role = create_iam_role(f"KarpenterNodeRole-{cluster_descriptor}", "Service", "ec2.amazonaws.com", karpenter_default_nodegroup_role_policy_arns)
karpenter_instance_profile = iam.InstanceProfile(f"KarpenterNodeInstanceProfile-{cluster_descriptor}",
    role=karpenter_node_role.name,
    name=f"KarpenterNodeInstanceProfile-{cluster_descriptor}"
)

# Create a Fargate profile service role:
fargate_profile_service_role = create_iam_role(f"{cluster_descriptor}-fargate-role", "Service", "eks-fargate-pods.amazonaws.com", default_fargate_pod_execution_role_policy)

# Create an EKS log group:
mtn_eks_loggroup = cloudwatch.LogGroup("mtn-eks-loggroup", 
    name=f"/aws/eks/{cluster_descriptor}/cluster",
    tags=general_tags,
    retention_in_days=1
)

# Create the cluster control plane and Fargate profiles:
mtn_eks_cluster = eks_provider.Cluster(f"eks-{cluster_descriptor}",
    name=f"{cluster_descriptor}",
    vpc_id=mtn_vpc.id,
    instance_role=karpenter_node_role,
    cluster_security_group=mtn_cluster_security_group,
    create_oidc_provider=True,
    version="1.24",
    instance_profile_name=karpenter_instance_profile,
    skip_default_node_group=True,
    service_role=eks_iam_role,
    provider_credential_opts=eks_provider.KubeconfigOptionsArgs(
        profile_name=config.profile,
    ),
    endpoint_private_access=True,
    endpoint_public_access=False,
    enabled_cluster_log_types=["api", "audit", "authenticator", "controllerManager", "scheduler"],
    #public_access_cidrs=["0.0.0.0/0"],
    subnet_ids=[s.id for s in mtn_eks_cp_subnets],
    tags={**general_tags, "Name": f"{cluster_descriptor}"},
    fargate=eks.FargateProfileArgs(
        cluster_name=f"{cluster_descriptor}",
        subnet_ids=[s.id for s in mtn_private_subnets],
        pod_execution_role_arn=fargate_profile_service_role.arn,
        selectors=[{"namespace": "karpenter"}, {"namespace": "flux-system"}, {"namespace": "kube-system"}]),
    opts=ResourceOptions(depends_on=[
            mtn_nodegroup_security_group,
            eks_iam_role,
            mtn_eks_loggroup
        ]))

mtn_eks_cluster_oidc_arn = mtn_eks_cluster.core.oidc_provider.arn
mtn_eks_cluster_oidc_url = mtn_eks_cluster.core.oidc_provider.url

# Create an IAM role for VPC CNI:
iam_role_vpc_cni_service_account = create_oidc_role(f"{cluster_descriptor}-aws-node", "kube-system", mtn_eks_cluster_oidc_arn, mtn_eks_cluster_oidc_url, "aws-node", cni_service_account_policy_arns)

# Create a Karpenter IAM role scoped to karpenter namespace
iam_role_karpenter_controller_policy = create_policy(f"{cluster_descriptor}-karpenter-policy", "karpenter_oidc_role_policy.json")
iam_role_karpenter_controller_service_account_role = create_oidc_role(f"{cluster_descriptor}-karpenter", "karpenter", mtn_eks_cluster_oidc_arn, mtn_eks_cluster_oidc_url, "karpenter", [iam_role_karpenter_controller_policy.arn])
export("karpenter-oidc-role-arn", iam_role_karpenter_controller_service_account_role.arn)


# Install VPC CNI addon when the cluster is initialized:
vpc_cni_addon = eks.Addon("vpc-cni-addon",
    cluster_name=f"{cluster_descriptor}",
    addon_name="vpc-cni",
    addon_version="v1.11.4-eksbuild.1",
    resolve_conflicts="OVERWRITE",
    service_account_role_arn=iam_role_vpc_cni_service_account.arn,
    opts=ResourceOptions(
        depends_on=[mtn_eks_cluster]
    )
)

# Install kube-proxy addon when the cluster is initialized:
kube_proxy_addon = eks.Addon("kube-proxy-addon",
    cluster_name=f"{cluster_descriptor}",
    addon_name="kube-proxy",
    addon_version="v1.24.7-eksbuild.2",
    resolve_conflicts="OVERWRITE",
    opts=ResourceOptions(
        depends_on=[mtn_eks_cluster, vpc_cni_addon]
    )
)

# Install CoreDNS addon when the cluster is initialized:
core_dns_addon = eks.Addon("coredns-addon",
    cluster_name=f"{cluster_descriptor}",
    addon_name="coredns",
    addon_version="v1.8.7-eksbuild.3",
    resolve_conflicts="OVERWRITE",
    opts=ResourceOptions(
        depends_on=[mtn_eks_cluster, vpc_cni_addon, kube_proxy_addon]
    )
)

# Create a kubernetes provider
role_provider = k8s.Provider(f"{cluster_descriptor}-kubernetes-provider",
    kubeconfig=mtn_eks_cluster.kubeconfig,
    opts=ResourceOptions(depends_on=[mtn_eks_cluster])
)

# Create a karpenter namespace:
karpenter_namespace = k8s.core.v1.Namespace("karpenter-namespace",
    metadata={"name": "karpenter"},
    opts=ResourceOptions(
        provider=role_provider,
        depends_on=[mtn_eks_cluster]
    )
)

pulumi.export('kubeconfig', kubeconfig)