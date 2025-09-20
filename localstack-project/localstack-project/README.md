# README.md

# LocalStack Project

This project is designed for local development and testing of AWS services using LocalStack. It provides a set of services that mimic AWS functionalities, allowing developers to build and test applications without incurring costs or needing an internet connection.

## Project Structure

```
localstack-project
├── src
│   ├── services
│   │   ├── s3.ts
│   │   ├── sqs.ts
│   │   └── lambda.ts
│   ├── tests
│   │   └── integration
│   │       └── services.test.ts
│   └── utils
│       └── localstack-client.ts
├── docker-compose.yml
├── localstack-config.json
├── package.json
├── tsconfig.json
└── README.md
```

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd localstack-project
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start LocalStack:**
   ```bash
   docker-compose up
   ```

## Usage

- **S3 Service:** Interact with the S3 service using the `S3Service` class. Methods include:
  - `createBucket`
  - `uploadFile`
  - `listBuckets`

- **SQS Service:** Use the `SQSService` class to manage SQS queues. Methods include:
  - `sendMessage`
  - `receiveMessage`
  - `deleteMessage`

- **Lambda Service:** Deploy and invoke Lambda functions with the `LambdaService` class. Methods include:
  - `createFunction`
  - `invokeFunction`

## Testing

Integration tests are provided in the `src/tests/integration/services.test.ts` file. Run the tests using:
```bash
npm test
```

## Configuration

The `localstack-config.json` file contains configuration settings for LocalStack, specifying which AWS services to enable.

## License

This project is licensed under the MIT License.