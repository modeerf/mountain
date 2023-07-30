{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
              "ec2:CreateLaunchTemplate",
              "ec2:CreateFleet",
              "ec2:RunInstances",
              "ec2:CreateTags",
              "iam:PassRole",
              "ec2:TerminateInstances",
              "ec2:DeleteLaunchTemplate",
              "ec2:DescribeLaunchTemplates",
              "ec2:DescribeInstances",
              "ec2:DescribeSecurityGroups",
              "ec2:DescribeSubnets",
              "ec2:DescribeInstanceTypes",
              "ec2:DescribeInstanceTypeOfferings",
              "ec2:DescribeAvailabilityZones",
              "ec2:DescribeSpotPriceHistory",
              "ssm:GetParameter",
              "pricing:GetProducts"
            ],
            "Resource": "*",
            "Effect": "Allow"
        }
    ]
}