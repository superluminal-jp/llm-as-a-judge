#!/usr/bin/env python3
"""Setup configuration for LLM-as-a-Judge package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements from requirements.txt
requirements = (this_directory / "requirements.txt").read_text().strip().split('\n')
requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]

setup(
    name="llm-as-a-judge",
    version="0.1.0",
    author="LLM Judge Team",
    author_email="team@llm-judge.dev",
    description="A production-ready LLM-as-a-Judge system for evaluating language model outputs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/llm-as-a-judge",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Linguistic",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "http": [
            "httpx>=0.25.0",
            "aiohttp>=3.8.0",
        ],
        "monitoring": [
            "prometheus-client>=0.15.0",
            "structlog>=23.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "llm-judge=llm_judge.presentation.cli:cli_entry",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/your-org/llm-as-a-judge/issues",
        "Source": "https://github.com/your-org/llm-as-a-judge",
        "Documentation": "https://github.com/your-org/llm-as-a-judge/blob/main/docs/README.md",
    },
    keywords=[
        "llm", 
        "evaluation", 
        "ai", 
        "nlp", 
        "machine-learning", 
        "openai", 
        "anthropic",
        "domain-driven-design",
        "clean-architecture"
    ],
    include_package_data=True,
    package_data={
        "llm_judge": [
            "py.typed",  # Indicates this package has type hints
        ],
    },
    zip_safe=False,
)