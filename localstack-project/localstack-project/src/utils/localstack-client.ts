import AWS from 'aws-sdk';

export const createLocalStackClient = (service: string) => {
    const endpoint = 'http://localhost:4566'; // LocalStack endpoint
    const options = {
        endpoint,
        s3ForcePathStyle: true, // Needed for S3
        accessKeyId: 'test', // Dummy credentials
        secretAccessKey: 'test', // Dummy credentials
    };

    switch (service) {
        case 's3':
            return new AWS.S3(options);
        case 'sqs':
            return new AWS.SQS(options);
        case 'lambda':
            return new AWS.Lambda(options);
        default:
            throw new Error(`Service ${service} is not supported.`);
    }
};