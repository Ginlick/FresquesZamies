# Fresques Zamies
Fresques Zamies is a service managing events in the sustainability domain.

To set up the website, follow these steps.
## 1. Copy Files
Import the repo in a folder on your server. Set the server root to the "[repo folder]/src" folder.
## 2. Set up Information
(note: this is not done currently)

Create a "server-info.json" file, as shown in the "templates" folder.

### MySQL Database
Create a MySQL database on your server, and create a table "events". It will need three columns: date VARCHAR(999), description VARCHAR(999), lien VARCHAR(999).

Then, complete the required information in the server-info file; namely, the ...
