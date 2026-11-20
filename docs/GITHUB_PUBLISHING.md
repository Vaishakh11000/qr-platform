# GitHub repository and downloads

The project source is published at [Vaishakh11000/qr-platform](https://github.com/Vaishakh11000/qr-platform). Use GitHub's **Code → Download ZIP** to download the source, or clone it with Git. To run the application on another computer, follow the fresh-laptop instructions in the root [README](../README.md).

The repository includes the backend, administrator console, public site, database migrations, deployment files, documentation, sample product seed data and media, and admin/public website screenshots. Local secrets, `.env` files, certificates and private keys, database backups, local media uploads, dependencies, and build output are excluded. The provided source ZIP is also excluded because its expanded catalogue data is already included.

The included VINSAK seed data is a sample, not a database backup. Importing it creates draft catalogue records; it does not transfer this computer's database, admin account, QR allocations, regions, policies, scans, or uploaded media. Product media licensing has not been confirmed; review `backend/data/vinsak_seed/README.md` before public redistribution.

## Updating the repository

Use the normal branch and pull request workflow for future changes:

```sh
git clone https://github.com/Vaishakh11000/qr-platform.git
cd qr-platform
git switch -c describe-your-change
# edit and review files
git add <intended-files>
git diff --cached --stat
git diff --cached --check
git commit -m "Describe the change"
git push -u origin describe-your-change
```

Open a pull request on GitHub to merge the branch into `main`. Keep real credentials, access tokens, database dumps, local uploads, and private keys out of commits. Do not use force-push to replace shared history.
