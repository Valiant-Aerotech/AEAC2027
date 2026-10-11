from setuptools import find_packages, setup

package_name = "mission"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Devansh",
    maintainer_email="54031999+devanshhdalal@users.noreply.github.com",
    description="Survey clocks, clusters, report, track CSV, boundary, and the 100 m standoff.",
    license="Proprietary",
)
