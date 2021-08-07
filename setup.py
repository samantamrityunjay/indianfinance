from setuptools import setup, find_packages

from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

VERSION = '0.0.2' 
DESCRIPTION = 'Indian Financial Markets'
# LONG_DESCRIPTION = 'Various tools for Indian Financial Markets'

# Setting up
setup(
        name="indianfinance", 
        version=VERSION,
        python_requires='>=3.5',
        author="Mrityunjay Samanta",
        author_email="samantamrityunjay98@gmail.com",
        description=DESCRIPTION,
        long_description=long_description,
        long_description_content_type="text/markdown",
        packages=find_packages(),
        install_requires=["requests"], # add any additional packages that 
        # needs to be installed along with your package. Eg: 'caer'
        
        keywords=['python', 'financials'],
        classifiers= [
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Education",
            "Intended Audience :: Financial",
            "Programming Language :: Python :: 3"
            "Operating System :: MacOS",
            "Operating System :: Microsoft :: Windows",
            "Operating System :: Ubuntu",
        ]
)