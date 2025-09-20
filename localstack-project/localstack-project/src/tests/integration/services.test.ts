import { S3Service } from '../../services/s3';
import { SQSService } from '../../services/sqs';
import { LambdaService } from '../../services/lambda';

describe('Integration Tests for AWS Services with LocalStack', () => {
    let s3Service: S3Service;
    let sqsService: SQSService;
    let lambdaService: LambdaService;

    beforeAll(async () => {
        s3Service = new S3Service();
        sqsService = new SQSService();
        lambdaService = new LambdaService();
    });

    test('S3: Create Bucket', async () => {
        const bucketName = 'test-bucket';
        await s3Service.createBucket(bucketName);
        const buckets = await s3Service.listBuckets();
        expect(buckets).toContain(bucketName);
    });

    test('SQS: Send Message', async () => {
        const queueUrl = await sqsService.createQueue('test-queue');
        const message = 'Hello, LocalStack!';
        await sqsService.sendMessage(queueUrl, message);
        const receivedMessage = await sqsService.receiveMessage(queueUrl);
        expect(receivedMessage).toEqual(message);
    });

    test('Lambda: Create and Invoke Function', async () => {
        const functionName = 'testFunction';
        await lambdaService.createFunction(functionName);
        const response = await lambdaService.invokeFunction(functionName);
        expect(response).toBeDefined();
    });
});