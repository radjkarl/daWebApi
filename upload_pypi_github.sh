#PYPI
######
#upload
python setup.py sdist upload
python setup.py bdist_wheel upload

#GIT
#####
git add -A #add all new files to the repo.
git commit -m "next version" #commit changes locally - set argument as message
git push origin master # Sends your commits in the "master" branch to GitHub

read -p "DONE"