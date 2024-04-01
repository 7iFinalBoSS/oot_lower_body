from setuptools import setup, find_packages

setup(
    name="oot_diffusion",
    version="0.0.1",
    description="A description of your project",
    author="Devanshu Lonarkar",
    author_email="gretelonarkar@gmail.com",
    url="https://github.com/7iFinalBoSS/oot_lower_body",
    packages=find_packages(include=["oot_diffusion", "oot_diffusion.*"]),
    include_package_data=True,
    install_requires=[
        "torch",
        "torchvision",
        "numpy",
        "scipy",
        "scikit-image",
        "opencv-python",
        "pillow",
        "diffusers==0.24.0",
        "transformers",
        "accelerate",
        "tqdm",
        "ultralytics",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Apache 2.0",
        "Programming Language :: Python :: 3.10",
    ],
)