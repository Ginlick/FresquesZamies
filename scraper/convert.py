import sheets
from jinja2 import Environment, PackageLoader, select_autoescape
import csv
import datetime


def main():
    events = []
    for organizer in ["FZC", "OPF"]:
        events.extend(sheets.get_manual_events("Calendrier: " + organizer, organizer))

    env = Environment(
        loader=PackageLoader("convert"),
        autoescape=False,  # TODO: replace with select_autoescape()
    )
    description_template = env.get_template("odoo.html")

    with open("odoo.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        writer.writerow(
            [
                "id",
                "date_begin",
                "date_end",
                "address_id",
                "user_id",
                "stage_id",
                "name",
                "description","tag_ids",
            ]
        )
        for event in events:
            organizer_name = "One Planet Friends"
            organizer_url = "http://oneplanetfriends.org/"
            address_id = event.location
            if event.organizer == "OPF":
                if event.location == "WWF Schweiz, Hohlstrasse 110, 8004 Zürich":
                    address_id = "WWF Schweiz"
            if event.organizer == "FZC":
                organizer_name = "Fresques Zamies & Co"
                organizer_url = "https://fresqueszamies.ch/"
                if (
                    event.location
                    == "Espace de coworking SEV52 - Avenue de Sévelin, 52"
                ):
                    address_id = "SEV52"
            # TODO: start and end times should be parsed from the event
            date_start = datetime.datetime(
                event.date.year, event.date.month, event.date.day, 18, 30
            )
            date_end = datetime.datetime(
                event.date.year, event.date.month, event.date.day, 21, 30
            )
            writer.writerow(
                [
                    event.organizer.casefold()
                    + "_"
                    + event.name.casefold().translate(str.maketrans(" ", "_"))
                    + "_"
                    + event.date.strftime("%Y%m%d%H%M")
                    + "_"
                    + event.language,
                    date_start.strftime("%Y-%m-%d %H:%M:00"),
                    date_end.strftime("%Y-%m-%d %H:%M:00"),
                    address_id,
                    "Jeffrey Belt",
                    "Annoncé",
                    event.name,
                    "".join(
                        description_template.render(
                            {
                                "organizer_name": organizer_name,
                                "organizer_url": organizer_url,
                                "event_url": event.url,
                            }
                        ).splitlines()
                    ),
                    "Fresque"
                ]
            )


if __name__ == "__main__":
    main()
