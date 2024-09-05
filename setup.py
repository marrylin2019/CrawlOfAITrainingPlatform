from setuptools import setup, find_packages

setup(
    name='your_project_name',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'paramiko',
        'requests',
        'pycryptodome',
        'curses'
    ],
    entry_points={
        'console_scripts': [
            'your_command=src.main:main',
        ],
    },
    author='Your Name',
    author_email='your_email@example.com',
    description='A brief description of your project',
    # url='https://github.com/yourusername/yourproject',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
