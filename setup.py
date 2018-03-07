from setuptools import setup

setup(name='amanuensis',
      version='0.1',
      description='Gather GH issues and put into ZH milestone.',
      url='http://github.com/briandailey/amanuensis',
      author='Brian Dailey',
      author_email='github@dailytechnology.net',
      license='MIT',
      packages=['.'],
      install_requires=[
          'requests==2.18.4',
          'click==6.7',
          'urllib3==1.22',
      ],
      # scripts=['bin/amanuensis', ]
      entry_points={
          'console_scripts': ['amanuensis=amanuensis:cli'],
      },
      zip_safe=False)
