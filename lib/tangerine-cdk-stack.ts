import * as cdk from '@aws-cdk/core';
import * as apigateway from '@aws-cdk/aws-apigateway';
import * as lambda from '@aws-cdk/aws-lambda';
import * as custom from './myconstants';
import * as sm from "@aws-cdk/aws-secretsmanager";
import * as iam from "@aws-cdk/aws-iam";

export class TangerineCdkStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, {
      env: { 
            region: custom.region,
            account: custom.account, },
    });

    const secretsManagerReadWriteRole = new iam.PolicyStatement();
    secretsManagerReadWriteRole.addActions(
      "secretsmanager:*",
      "cloudformation:CreateChangeSet",
      "cloudformation:DescribeChangeSet",
      "cloudformation:DescribeStackResource",
      "cloudformation:DescribeStacks",
      "cloudformation:ExecuteChangeSet",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSubnets",
      "ec2:DescribeVpcs",
      "kms:DescribeKey",
      "kms:ListAliases",
      "kms:ListKeys",
      "lambda:ListFunctions",
      "rds:DescribeDBClusters",
      "rds:DescribeDBInstances",
      "redshift:DescribeClusters",
      "tag:GetResources"
    );
    secretsManagerReadWriteRole.addResources("*");

    const secretsManagerLambda = new iam.PolicyStatement();
    secretsManagerLambda.addActions(
      "lambda:AddPermission",
      "lambda:CreateFunction",
      "lambda:GetFunction",
      "lambda:InvokeFunction",
      "lambda:UpdateFunctionConfiguration"
    );
    secretsManagerLambda.addResources("arn:aws:lambda:*:*:function:SecretsManager*");

    const secretsManagerServerless = new iam.PolicyStatement();
    secretsManagerServerless.addActions(
      "serverlessrepo:CreateCloudFormationChangeSet",
      "serverlessrepo:GetApplication"
    );
    secretsManagerServerless.addResources("arn:aws:serverlessrepo:*:*:applications/SecretsManager*");

    const secretsManagerS3 = new iam.PolicyStatement();
    secretsManagerS3.addActions(
      "s3:GetObject"
    );
    secretsManagerS3.addResources(
      "arn:aws:s3:::awsserverlessrepo-changesets*",
      "arn:aws:s3:::secrets-manager-rotation-apps-*/*"
    )

    const SESRole = new iam.PolicyStatement();
    SESRole.addActions(
      "ses:SendEmail",
      "ses:SendRawEmail"
    );
    SESRole.addResources("*");

    const handler = new lambda.Function(this, "tangerineCDKHandler", {
      runtime: lambda.Runtime.PYTHON_3_7, 
      code: lambda.Code.fromAsset("lambda-code"),
      handler: "lambda_function.lambda_handler"
    });

    handler.addToRolePolicy(secretsManagerReadWriteRole); 
    handler.addToRolePolicy(secretsManagerLambda);
    handler.addToRolePolicy(secretsManagerServerless);
    handler.addToRolePolicy(secretsManagerS3);
    handler.addToRolePolicy(SESRole);

    const api = new apigateway.RestApi(this, "tangerine-api", {
      restApiName: "TangerineCDKAPI",
      description: "This triggers a lambda function."
    });

    const postLambdaIntegration = new apigateway.LambdaIntegration(handler, {
      requestTemplates: { "application/json": '{ "statusCode": "200" }' }
    });

    api.root.addMethod("POST", postLambdaIntegration);

    const secret = new sm.CfnSecret(this, "tangerine-cdk-secret", {
      name: 'tangerine-cdk-test-secret',
      secretString: JSON.stringify(custom.secret)
    });

    

  }
}
