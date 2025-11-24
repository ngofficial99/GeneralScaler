from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="generalscaler-operator",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A generic Kubernetes autoscaling operator with pluggable metrics and policies",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/generalscaler-operator",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "kopf>=1.37.2",
        "kubernetes>=31.0.0",
        "prometheus-api-client>=0.5.5",
        "redis>=5.2.1",
        "google-cloud-pubsub>=2.26.1",
        "pydantic>=2.10.4",
        "pyyaml>=6.0.2",
        "python-json-logger>=3.2.1",
    ],
    extras_require={
        "dev": [
            "pytest>=8.3.4",
            "pytest-asyncio>=0.24.0",
            "pytest-cov>=6.0.0",
            "black>=24.10.0",
            "flake8>=7.1.1",
            "mypy>=1.13.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "generalscaler-operator=generalscaler.operator:main",
        ],
    },
)
