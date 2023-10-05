import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='anonfaces',
    version='1.0.3',
    author='Martin Drawitsch',
    author_email='martin.drawitsch@gmail.com',
    description='Video anonymization by face detection',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/StealUrKill/anonfaces',
    packages=setuptools.find_packages(),
    entry_points={'console_scripts': [
        'anonfaces = anonfaces.anonfaces:main',
    ]},
    package_data={'anonfaces': ['centerface.onnx']},
    include_package_data=True,
    install_requires=[
        'imageio',
        'imageio-ffmpeg',
        'numpy',
        'tqdm',
        'scikit-image',
        'opencv-python',
    ],
    extras_require={
        'gpu':  ['onnxruntime-gpu'],
        'Audio_Distortion':  ['pedalboard'],
        'Audio_Splicing':   ['moviepy'],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
