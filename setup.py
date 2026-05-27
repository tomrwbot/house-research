from setuptools import setup, find_packages

setup(
    name='house-research',
    version='0.1.0',
    description='Property research tools including amenity scoring',
    author='Tom',
    packages=find_packages(),
    python_requires='>=3.8',
    install_requires=[
        'requests>=2.28.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
        ]
    },
    entry_points={
        'console_scripts': [
            'amenity-scorer=scripts.amenity_scorer:main',
        ],
    },
)
