from setuptools import setup, find_packages

VERSION = '0.0.1' 
DESCRIPTION = 'Indian Financial Markets'
LONG_DESCRIPTION = 'Various tools for Indian Financial Markets'

# Setting up
setup(
       # the name must match the folder name 'verysimplemodule'
        name="indianfinance", 
        version=VERSION,
        author="Mrityunjay Samanta",
        author_email="samantamrityunjay98@gmail.com",
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        packages=find_packages(),
        install_requires=["requests"], # add any additional packages that 
        # needs to be installed along with your package. Eg: 'caer'
        
        keywords=['python', 'financials'],
        classifiers= [
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Education",
            "Programming Language :: Python :: 3"
        ]
)