from setuptools import setup, find_packages

setup(
    name="rag_module",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "pinecone-client==3.2.2",
        "google-generativeai",
        "langchain",
        "langchain-text-splitters",
        "python-dotenv",
        "pytest",
        "httpx"
    ],
)