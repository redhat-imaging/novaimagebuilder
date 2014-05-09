sdist:
	python setup.py sdist

signed-rpm: sdist
	rpmbuild -ba nova-image-builder.spec --sign --define "_sourcedir `pwd`/dist"

rpm: sdist
	rpmbuild -ba nova-image-builder.spec --define "_sourcedir `pwd`/dist"

srpm: sdist
	rpmbuild -bs nova-image-builder.spec --define "_sourcedir `pwd`/dist"

pylint:
	pylint --rcfile=pylint.conf nova-install

unittests:
	python -m unittest discover -v

clean:
	rm -rf MANIFEST build dist nova-image-builder.spec
