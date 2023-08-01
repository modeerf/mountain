import pulumi
from pulumi_aws import ec2, config, get_availability_zones
from settings import general_tags, cluster_descriptor, mtn_vpc_cidr, mtn_private_subnet_cidrs, mtn_public_subnet_cidrs, mtn_eks_cp_subnet_cidrs

"""
Creates a minium of AWS networking objects required for the mtn stack to work
"""

# Create a VPC and Internet Gateway:
mtn_vpc = ec2.Vpc("mtn-vpc",
    cidr_block=mtn_vpc_cidr,
    enable_dns_hostnames=True,
    enable_dns_support=True,
    tags={**general_tags, "Name": f"mtn-vpc-{config.region}"}
)

mtn_igw = ec2.InternetGateway("mtn-igw",
    vpc_id=mtn_vpc.id,
    tags={**general_tags, "Name": f"mtn-igw-{config.region}"},
    opts=pulumi.ResourceOptions(parent=mtn_vpc)
)

# Create a default any-any security group for mtn purposes:
mtn_sg = ec2.SecurityGroup("mtn-security-group",
    description="Allow any-any",
    vpc_id=mtn_vpc.id,
    ingress=[ec2.SecurityGroupIngressArgs(
        description="Any",
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        ipv6_cidr_blocks=["::/0"],
    )],
    egress=[ec2.SecurityGroupEgressArgs(
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        ipv6_cidr_blocks=["::/0"],
    )],
    tags={**general_tags, "Name": f"mtn-sg-{config.region}"},
    opts=pulumi.ResourceOptions(parent=mtn_vpc)
)

# Create subnets:
mtn_azs = get_availability_zones(state="available").names
mtn_public_subnets = []
mtn_private_subnets = []
mtn_eks_cp_subnets = []

for i in range(2):
    prefix = f"{mtn_azs[i]}"
    
    mtn_public_subnet = ec2.Subnet(f"mtn-public-subnet-{prefix}",
        vpc_id=mtn_vpc.id,
        cidr_block=mtn_public_subnet_cidrs[i],
        availability_zone=mtn_azs[i],
        tags={**general_tags, "Name": f"mtn-public-subnet-{prefix}"},
        opts=pulumi.ResourceOptions(parent=mtn_vpc)
    )
    
    mtn_public_subnets.append(mtn_public_subnet)

    mtn_public_route_table = ec2.RouteTable(f"mtn-public-rt-{prefix}",
        vpc_id=mtn_vpc.id,
        tags={**general_tags, "Name": f"mtn-public-rt-{prefix}"},
        opts=pulumi.ResourceOptions(parent=mtn_public_subnet)
    )
    
    mtn_public_route_table_association = ec2.RouteTableAssociation(f"mtn-public-rt-association-{prefix}",
        route_table_id=mtn_public_route_table.id,
        subnet_id=mtn_public_subnet.id,
        opts=pulumi.ResourceOptions(parent=mtn_public_subnet)
    )

    mtn_public_wan_route = ec2.Route(f"mtn-public-wan-route-{prefix}",
        route_table_id=mtn_public_route_table.id,
        gateway_id=mtn_igw.id,
        destination_cidr_block="0.0.0.0/0",
        opts=pulumi.ResourceOptions(parent=mtn_public_subnet)
    )

    mtn_eip = ec2.Eip(f"mtn-eip-{prefix}",
        tags={**general_tags, "Name": f"mtn-eip-{prefix}"},
        opts=pulumi.ResourceOptions(parent=mtn_vpc)
    )
    
    mtn_nat_gateway = ec2.NatGateway(f"mtn-nat-gateway-{prefix}",
        allocation_id=mtn_eip.id,
        subnet_id=mtn_public_subnet.id,
        tags={**general_tags, "Name": f"mtn-nat-{prefix}"},
        opts=pulumi.ResourceOptions(depends_on=[mtn_vpc])
    )

    mtn_private_subnet = ec2.Subnet(f"mtn-private-subnet-{prefix}",
        vpc_id=mtn_vpc.id,
        cidr_block=mtn_private_subnet_cidrs[i],
        availability_zone=mtn_azs[i],
        tags={**general_tags, "Name": f"mtn-private-subnet-{prefix}", "karpenter.sh/discovery": f"{cluster_descriptor}"},
        opts=pulumi.ResourceOptions(parent=mtn_vpc)
    )
    
    mtn_private_subnets.append(mtn_private_subnet)

    mtn_private_route_table = ec2.RouteTable(f"mtn-private-rt-{prefix}",
        vpc_id=mtn_vpc.id,
        tags={**general_tags, "Name": f"mtn-private-rt-{prefix}"},
        opts=pulumi.ResourceOptions(parent=mtn_private_subnet)
    )
    
    mtn_private_route_table_association = ec2.RouteTableAssociation(f"mtn-private-rt-association-{prefix}",
        route_table_id=mtn_private_route_table.id,
        subnet_id=mtn_private_subnet.id,
        opts=pulumi.ResourceOptions(parent=mtn_private_subnet)
    )

    mtn_private_wan_route = ec2.Route(f"mtn-private-wan-route-{prefix}",
        route_table_id=mtn_private_route_table.id,
        nat_gateway_id=mtn_nat_gateway.id,
        destination_cidr_block="0.0.0.0/0",
        opts=pulumi.ResourceOptions(parent=mtn_private_subnet)
    )

    mtn_eks_cp_subnet = ec2.Subnet(f"mtn-eks-cp-subnet-{prefix}",
        vpc_id=mtn_vpc.id,
        cidr_block=mtn_eks_cp_subnet_cidrs[i],
        availability_zone=mtn_azs[i],
        tags={**general_tags, "Name": f"mtn-eks-cp-subnet-{prefix}"},
        opts=pulumi.ResourceOptions(parent=mtn_vpc)
    )
    
    mtn_eks_cp_subnets.append(mtn_eks_cp_subnet)

    mtn_eks_cp_route_table = ec2.RouteTable(f"mtn-eks-cp-rt-{prefix}",
        vpc_id=mtn_vpc.id,
        tags={**general_tags, "Name": f"mtn-eks-cp-rt-{prefix}"},
        opts=pulumi.ResourceOptions(parent=mtn_eks_cp_subnet)
    )
    
    mtn__eks_cp_route_table_association = ec2.RouteTableAssociation(f"mtn-eks-cp-rt-association-{prefix}",
        route_table_id=mtn_eks_cp_route_table.id,
        subnet_id=mtn_eks_cp_subnet.id,
        opts=pulumi.ResourceOptions(parent=mtn_eks_cp_subnet)
    )

    mtn_eks_cp_wan_route = ec2.Route(f"mtn-eks-cp-wan-route-{prefix}",
        route_table_id=mtn_eks_cp_route_table.id,
        nat_gateway_id=mtn_nat_gateway.id,
        destination_cidr_block="0.0.0.0/0",
        opts=pulumi.ResourceOptions(parent=mtn_eks_cp_subnet)
    )