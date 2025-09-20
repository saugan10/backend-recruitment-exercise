import { S3 } from 'aws-sdk';

export class S3Service {
    private s3: S3;

    constructor() {
        this.s3 = new S3({
            endpoint: 'http://localhost:4566', // LocalStack endpoint
            s3ForcePathStyle: true, // Needed for LocalStack
        });
    }

    async createBucket(bucketName: string): Promise<S3.CreateBucketOutput> {
        return this.s3.createBucket({ Bucket: bucketName }).promise();
    }

    async uploadFile(bucketName: string, key: string, body: Buffer | string): Promise<S3.PutObjectOutput> {
        return this.s3.upload({ Bucket: bucketName, Key: key, Body: body }).promise();
    }

    async listBuckets(): Promise<S3.Bucket[]> {
        const response = await this.s3.listBuckets().promise();
        return response.Buckets || [];
    }
}