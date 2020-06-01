import os

from setuptools import find_packages, setup


def get_version():
    version_file_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(version_file_path, "VERSION")) as file:
        version = file.read().strip()
    return version.strip()


def get_long_description():
    readme_file_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(readme_file_path, "README.md")) as file:
        long_description = file.read()
    return long_description


setup(
    name="banlimit",
    version=get_version(),
    description="",
    long_description=get_long_description(),
    data_files=[
        ("version", ["VERSION"]),
        ("readme", ["README.md"])
    ],
    url="https://github.com/adityakrgupta25/banlimit/tree/master",
    author="Aditya Gupta",
    author_email="holaditya@gmail.com",
    license="Proprietor License",
    keywords="utilities",
    packages=find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]
    ),
    install_requires=[
        "django>=2.2",
        "django-ratelimit==2.00",
        "requests>=2.22.0",
        "importlib-metadata==1.3.0"
    ],
    project_urls={
        "Source": "",  # noqa
        "Documentation": "https://github.com/Instamojo/instamojo-pypi/blob/im-toolbox/master/README.md",  # noqa
    },
    classifiers=[
        "Intended Audience :: Instamojo Developers",
        "License :: Proprietor License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ]
)