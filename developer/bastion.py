
import pulumi_awsx as awsx
import pulumi
from vpc import mtn_vpc, mtn_public_subnets, mtn_eks_cp_subnets
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


# Get the stack name for generating the key pair name
stack_name = pulumi.get_stack()



private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)

private_key_pass = b"your-password"

encrypted_pem_private_key = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.BestAvailableEncryption(private_key_pass)
)

pem_public_key = private_key.public_key().public_bytes(
  encoding=serialization.Encoding.PEM,
  format=serialization.PublicFormat.SubjectPublicKeyInfo
)

private_key_file = open(stack_name + ".pem", "w")
private_key_file.write(encrypted_pem_private_key.decode())
private_key_file.close()

public_key_file = open(stack_name + ".pub", "w")
public_key_file.write(pem_public_key.decode())
public_key_file.close()

# Create an AWS key pair resource
key_pair = aws.ec2.KeyPair( key_name=stack_name, public_key=pem_public_key.decode() ) # Use stack name as the key name

# Export the public key for the key pair
pulumi.export("public_key", key_pair.key_name)

# Create a security group for the bastion host to allow SSH traffic
bastion_sg = aws.ec2.SecurityGroup("bastion-security-group",
    vpc_id=mtn_vpc.id,
    ingress=[
        {
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "cidr_blocks": ["0.0.0.0/0"],  # Allow SSH from anywhere (for demo purposes)
        },
    ],
)

# Create the bastion host instance in the public subnet
bastion_host = aws.ec2.Instance("bastion-host",
    instance_type="t2.micro",
    ami="ami-0c55b159cbfafe1f0",  # Replace with your preferred AMI ID
    subnet_id=mtn_public_subnet.id,
    key_name=key_pair.key_name,
    vpc_security_group_ids=[bastion_sg.id],
)

# Export the public IP of the bastion host for easy access
pulumi.export("bastion_public_ip", bastion_host.public_ip)
