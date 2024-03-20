import argparse
from typing import Tuple, List
from babel.dates import format_date
from jinja2 import Environment, PackageLoader, select_autoescape
import datetime
import dateparser
import json
import arrow
import math
import os
import re
import base64
import requests
import string
import json
from ics import Calendar
import requests
from bs4 import BeautifulSoup
from requests_html import HTMLSession
import sheets

# TODO: replace the tuples in this code with dictionaries using these keys.
KEY_TITLE = "title"
KEY_NAME = "name"
KEY_DATE = "date"
KEY_PLACE = "place"
KEY_URL = "url"
KEY_LANGUAGE = "language"
KEY_CITY = "city"
KEY_LINGUISTIC_REGION = "lregion"
KEY_ORGANIZER = "organizer"

KEY_ELEMENT_ID = "id"
KEY_LANG_EN = "en"
KEY_LANG_FR = "fr"


# Returns a Date object (at midnight) for the given strptime format, or None on failure.
# If the year is not parsed (1900), it's set to the current year.
# https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
def maybeParseDate(date_string, format):
    try:
        dt = datetime.datetime.strptime(date_string, format)
        date = dt.date()
        if date.year == 1900:
            return datetime.date(datetime.datetime.today().year, date.month, date.day)
        return date
    except ValueError:
        return None


# All the scrape_ functions below extract events from various ticketing sytem pages.
# soup: BeautifulSoup object, see https://www.crummy.com/software/BeautifulSoup/bs4/doc/
# Return: array of tuples (title, event name, date, place, url, language)


# TODO: remove this function. It's here for backwards compatibility.
# (title, event name, date, place, url, language) -> Event
def tuple_to_event(
    tuple: Tuple[str, str, datetime.date, str, str, str]
) -> sheets.Event:
    return sheets.Event(
        name=tuple[0],
        date=tuple[2],
        location=tuple[3],
        url=tuple[4],
        language=tuple[5],
    )


# BilletWeb
def scrape_BilletWeb(soup, title, language):
    events = []
    for tag in soup.find_all("div", class_="multi_event_container"):
        child = tag.find("div", class_="multi_event_info_empty")
        if child:
            continue  # this container is empty

        child = tag.find("span", class_="multi_event_name_span")
        if not child:
            if not "multi_event_info_empty" in tag["class"]:
                print("BilletWeb name not found? ", tag)
            continue
        name = child.string
        if "FORMATION ANIMATION" in name.upper():
            print("Seems to be a facilitator training, skipping:", name)
            continue

        child = tag.find("div", class_="multi_event_date")
        if child is None:
            print("Date not found?", tag)
            continue
        child2 = child.span
        if child2 is None:
            print("unexpected date:", child)
        date_strings = []  # deal with multi-dates
        for child3 in child2.find_all("span", class_="multi_event_time"):
            date_strings.append(child3.string)
        if len(date_strings) == 0:
            date_strings.append(child2.string)
        dates = []
        for date_string in date_strings:
            # TODO: there has got to be better ways to parse these strings.
            date = dateparser.parse(
                date_string,
                settings=dict(
                    {
                        "DATE_ORDER": "DMY",
                        "REQUIRE_PARTS": ["day", "month"],
                        "SKIP_TOKENS": [
                            "Mon",
                            "Tue",
                            "Wed",
                            "Thu",
                            "Fri",
                            "Sat",
                            "Sun",
                        ],
                    }
                ),
            )
            if not date:
                date = maybeParseDate(date_string, "%a %m/%d")  # ex: Sun 03/25
            if not date:
                date = maybeParseDate(
                    date_string[0:16], "%a %b %d, %Y"
                )  # ex: Sun Mar 03, 2023
            if not date:
                print(
                    "Cannot parse date, discarding event:",
                    date_string,
                    "(" + title + ")",
                )
                continue
            dates.append(date)

        child = tag.find("div", class_="multi_event_place")
        if not child:
            print("Place not found?", tag)
            continue
        place = child.span.string
        if not place:
            continue  # skip online-only events

        child = tag.find("div", class_="multi_event_button")
        if not child:
            print("No button found?", tag)
            continue
        child2 = child.find("a")
        if not child2:
            print("No URL found on button?", tag)
            continue
        url = child2["href"]
        if not url:
            print("Unable to extract URL?", tag)
            continue
        if url.strip() == "#":
            oc = child2["onclick"]
            if not oc:
                print("Unable to extract onclick?", tag)
                continue
            url = oc.split("'")[1]

        real_language = language
        if "Biodiversity Collage" in name:
            real_language = "en"
        for date in dates:
            events.append((title, name, date, place, url, real_language))
    return events


# BilletWeb
def scrape_BilletWebShop(soup, title, url, language):
    events = []
    for tag in soup.find_all("script"):
        if "json_session_data=JSON.parse" in tag.text:
            # This is incredibly fragile
            txt = tag.text
            s = "Base64.decode('"
            z = len(s)
            x = txt.find(s)
            y = txt.find("'))")
            convertsample = txt[x + z : y]

            # convert to a JSON dictionary
            convertbytes = convertsample.encode("ascii")
            convertedbytes = base64.b64decode(convertbytes)
            decodedsample = convertedbytes.decode("ascii")
            json_data = json.loads(decodedsample)

            # extract the events
            if json_data["status"] == "sold_out":
                break
            for ed in json_data["payload"]:
                date = datetime.date.fromtimestamp(ed["start_day"])
                place = ed["place"]
                events.append((title, title, date, place, url, language))
    return events


# Fresque du Climat: we truncate to the first three per language to avoid drowning out other workshops
def has_class_my3_only(tag):
    if not tag.name == "div":
        return False
    if not tag.has_attr("class"):
        return False
    classes = tag["class"]
    return len(classes) == 1 and classes[0] == "my-3"


def scrape_FresqueDuClimat(soup, title):
    events = []
    tag = soup.find(has_class_my3_only)
    max_count = 3
    for child in tag.find_all("a", class_="text-decoration-none")[:max_count]:
        if child.get("href") == "":
            continue  # no URL, the workshop is fully booked
        url = "https://association.climatefresk.org" + child.get("href")

        child2 = child.find("div", class_="flex-grow-1")
        divs = child2.find_all("div")

        # date, hour, place
        child4 = divs[0].find("small", class_="text-secondary")
        x = child4.text.split("·")
        date_string = x[0].strip()
        date = dateparser.parse(date_string).date()
        place = re.sub(r"\s+", " ", x[2].strip())

        # title, language
        child5 = divs[1]
        name_and_language = child5.text.strip()
        iLanguage = name_and_language.find("(")
        if iLanguage == -1:
            raise Exception("Cannot find language in workshop title: " + name)
        name = name_and_language[:iLanguage].strip()
        language = name_and_language[iLanguage:].strip()
        if language == "(Deutsch)":
            language = "de"
        elif language == "(English)":
            language = "en"
        elif language == "(Français)":
            language = "fr"
        else:
            raise Exception("Language not handled: " + language)

        events.append(
            sheets.Event(
                name=title,
                date=date,
                location=place,
                url=url,
                organizer="CF",
                language=language,
            )
        )
    return events


def is_EventBrite_location(tag):
    return (
        tag.name == "div"
        and tag.has_attr("data-subcontent-key")
        and tag.attrs["data-subcontent-key"] == "location"
    )


# EventBrite
def scrape_EventBrite(soup, title):
    events = []
    for tag in soup.find_all("ul", class_="cc-card-list"):
        for card in tag.find_all("li", class_="cc-card-list__item"):
            child = card.find("h3", class_="eds-event-card-content__title")
            if not child:
                raise Exception("Title element not found")
            inner = child.find("div", class_="eds-is-hidden-accessible")
            if not inner:
                raise Exception("Title text not found")
            name = inner.text

            child = card.find("div", class_="eds-event-card-content__sub-title")
            if not child:
                raise Exception("Subtitle element for date not found")
            date_string = child.text
            date = maybeParseDate(date_string[:11], "%a, %b %d")  # ex: Tue, Mar 21
            if not date:
                print(
                    "Cannot parse date, discarding event:",
                    date_string,
                    "(" + title + ")",
                )
                continue

            child = card.find(is_EventBrite_location)
            if not child:
                if "EN LIGNE" in name.upper():
                    continue
                raise Exception("Location element not found:", card)
            place = child.text

            child = card.find("a", class_="eds-event-card-content__action-link")
            if not child:
                raise Exception("Action link element for URL not found")
            url = child["href"]

            events.append(
                (
                    title,
                    name,
                    date,
                    place,
                    url,
                    "fr",
                )
            )
    return events


# ICAL format
def scrape_ICal(fp, url, title):
    events = []
    c = Calendar(requests.get(url).text)
    for e in c.events:
        if "Formation" in e.name:
            continue  # skip facilitation trainings
        if not e.location:
            continue  # skip online events
        if not "Suisse" in e.location:
            continue
        title = "Atelier GreenDonut"
        if "TEXTILE" in e.name.upper():
            title = "Fresque du Textile"
        elif "DECHETS" in e.name.upper():
            title = "Fresque des Déchets"
        events.append(
            sheets.Event(
                name=title,
                date=e.begin.datetime,
                location=e.location,
                url="https://calendar.google.com/calendar/u/0/embed?src=greendonut.info@gmail.com&ctz=Europe/Paris",
                language="fr",
            )
        )
    return events


# Watted, specifically PowerPlay
def is_Watted_event(tag):
    return (tag.name == "a") and (tag.text == "Infos et inscription")


def scrape_Watted_PowerPlay(soup):
    events = []
    for tag in soup.find_all(is_Watted_event):
        p = tag.parent
        t = p.text
        i = t.find(" :")
        tokens = t[0:i].split(",")
        date_string = tokens[1].strip()
        date = dateparser.parse(date_string).date()
        if not date:
            print("Skipping Watted event, unable to extract date from", date_string)
            continue
        location = ", ".join([x.strip() for x in tokens[2:] + [tokens[0]]])
        events.append(
            sheets.Event(
                name="Power Play",
                date=date,
                location=location,
                url=tag.get("href"),
                language="en" if "Zürich" in location else "fr",
            )
        )
    return events


# Given an array of events, filters for Switzerland and appends to each tuple the identified city.
# Input: array of (title, event name, date, place, url, language)
# Output: array of (title, event name, date, place, url, language, city)
def append_city_and_filter_for_switzerland(
    events: List[sheets.Event], debug: bool
) -> List[sheets.Event]:
    normalizer = str.maketrans("ÜÈÂ", "UEA")
    cities = dict()
    for c in (
        "Arosa",
        "Basel",
        "Bern",
        "Biel",
        "Bienne",
        "Bulle",
        "Divonne",
        "Dübendorf",
        "Estavayer",
        "Fribourg",
        "Genève",
        "Gland",
        "Kaufdorf",
        "Lausanne",
        "Le Grand-Saconnex",
        "Morges",
        "Neuchâtel",
        "Nyon",
        "Penthalaz",
        "Pully",
        "Rolle",
        "Sion",
        "St. Gallen",
        "St. Sulpice",
        "Vevey",
        "Zürich",
    ):
        cities[c.upper().translate(normalizer)] = c
    filtered = []
    for event in events:
        name = event.name
        place = event.location
        normalized_place = place.upper().translate(normalizer)

        if normalized_place.endswith("BELGIQUE"):
            continue

        city = None
        for normalized_city, c in cities.items():
            if (
                normalized_place.startswith(normalized_city)
                or re.search(r"[( ,]" + normalized_city, normalized_place)
            ) and not "FRANCE" in normalized_place:
                city = c
                break

        if not city and "SEV52" in normalized_place:
            city = "Lausanne"

        if not city:
            calendar = event.name
            if "Climate Fresk" in calendar or "Fresque du Climat" in calendar:
                raise Exception("Missed Swiss city:", place, "(" + name + ")")
            if debug:
                print("Discarding, not in Switzerland:", place, "(" + name + ")")
            continue

        if city == "Divonne":
            city = city + ' <img src="flags/icons8-fr-16.png" alt="fr"/>'
        event.city = city
        filtered.append(event)
    return filtered


# Refreshes the file at "filename", if at least a day behind "today", with the contents at "url".
def refresh_cache(filename, today, url):
    try:
        ts = os.path.getmtime(filename)
    except OSError:
        ts = 0
    filetime = datetime.datetime.fromtimestamp(ts)
    delta = today - filetime
    if delta.days >= 1:
        print('Refreshing "' + filename + '" from ' + url + ", date was", filetime)

        if url.startswith("https://www.eventbrite.com/"):
            session = HTMLSession()
            r = session.get(url)
            r.html.render()  # this call executes the js in the page
            with open(filename, "w") as f:
                print(r.html.find("ul.cc-card-list", first=True).html, file=f)
        else:
            r = requests.get(url)
            with open(filename, "w") as f:
                print(r.text, file=f)


# write events as JSON
def write_events_as_json(events: List[sheets.Event]):
    ae = []
    t = datetime.time(0, 0)
    for event in events:
        lregion = "Romandie"
        if event.city in (
            "Arosa",
            "Basel",
            "Bern",
            "Dübendorf",
            "Kaufdorf",
            "St. Gallen",
            "Zürich",
        ):
            lregion = "Deutschschweiz"
        elif event.city in ("Fribourg"):
            lregion = "Sarine"
        organizer = event.organizer
        de = {
            KEY_TITLE: event.name,
            KEY_NAME: event.name,
            KEY_DATE: math.floor(datetime.datetime.combine(event.date, t).timestamp()),
            KEY_PLACE: event.location,
            KEY_URL: event.url,
            KEY_LANGUAGE: event.language,
            KEY_CITY: event.city,
            KEY_LINGUISTIC_REGION: lregion,
            KEY_ORGANIZER: organizer,
        }
        ae.append(de)
    return ae


def main():
    # Parse the command-line flags.
    argParser = argparse.ArgumentParser()
    argParser.add_argument(
        "-c",
        "--cache_dir",
        default="cache",
        help="Directory where the HTML files are cached for 1 day to reduce host load.",
    )
    argParser.add_argument(
        "-ap",
        "--about_prefix",
        default=None,
        help="Output 'about' HTML files to write, disabled if left empty. Don't include the extension as the program will append _<language>.'",
    )
    argParser.add_argument(
        "-e",
        "--events_js",
        default=None,
        help="Output 'evemts' JavaScript file to write, disabled if left empty.",
    )
    argParser.add_argument(
        "-m",
        "--main_html",
        default=None,
        help="Output 'main' HTML file to write, disabled if left empty.",
    )
    argParser.add_argument(
        "-d", "--debug", default=False, help="Whether to output debug information."
    )
    args = argParser.parse_args()

    env = Environment(
        loader=PackageLoader("scrape"),
        autoescape=False,  # TODO: replace with select_autoescape()
    )

    # Set up the list of calendars we are going to read.
    workshops = sheets.get_workshops()
    # TODO: stop using calendars (list of tuples) in favor of workshops (list of classes)
    # Each tuple is (workshop name, calendar URL, language, main site)
    calendars = []
    for workshop in workshops:
        calendars.append(
            (
                workshop.title,
                workshop.calendar_link,
                workshop.language,
                workshop.site_link,
            )
        )
    calendars.sort(key=lambda c: c[0])  # sort by workshop name

    env = Environment(
        loader=PackageLoader("scrape"),
        autoescape=False,  # TODO: replace with select_autoescape()
    )
    today = datetime.datetime.today()

    if args.events_js:
        # Prepare cache.
        if not os.path.exists(args.cache_dir):
            os.mkdir(args.cache_dir)

        # Start with events we have manually authored.
        all_events = []
        for suffix in ["FZC", "extra"]:
            organizer = None if suffix == "extra" else suffix
            all_events.extend(
                sheets.get_manual_events(
                    "1totCMhD_sRcU1b3JNICTUWXcYoYPOjQRo9KLv8NW4x8",
                    "Calendrier: " + suffix + "!A1:I50",
                    "Workshop",
                    "Date",
                    "Location",
                    "Link",
                    "Languages",
                    "Visible",
                    organizer,
                )
            )
        all_events.extend(
            sheets.get_manual_events(
                "10XKUvvU_b-js3kC7Q25VrtYW-flt-qsvwvUThveusOo",
                "Agenda!A1:H50",
                "Workshop name",
                "Date",
                "Location",
                "Link",
                "Languages",
                "Live on oneplanetfriends.org",
                "OPF",
            )
        )
        print(len(all_events), "added manually.")

        # Add scraped events.
        for calendar in calendars:
            events = []
            title = calendar[0]
            url = calendar[1]
            language = calendar[2]

            # load and parse the file
            filename = os.path.join(args.cache_dir, title + "_" + language + ".html")
            refresh_cache(filename, today, url)
            with open(filename) as fp:
                if url.endswith(".ics") or url.startswith("https://framagenda.org/"):
                    events = scrape_ICal(fp, url, title)
                else:
                    soup = BeautifulSoup(fp, "html.parser")

                    # scrape the events depending on the ticketing platform
                    if url.startswith("https://www.billetweb.fr/shop.php"):
                        events = list(
                            map(
                                tuple_to_event,
                                scrape_BilletWebShop(soup, title, url, language),
                            )
                        )
                    elif url.startswith("https://www.billetweb.fr/"):
                        events = list(
                            map(tuple_to_event, scrape_BilletWeb(soup, title, language))
                        )
                    elif url.startswith("https://association.climatefresk.org/"):
                        events = scrape_FresqueDuClimat(soup, title)
                    elif url.startswith("https://www.eventbrite."):
                        events = list(
                            map(tuple_to_event, scrape_EventBrite(soup, title))
                        )
                    elif url.startswith("https://www.watted.ch/"):
                        events = scrape_Watted_PowerPlay(soup)
                    else:
                        raise Exception("URL not handled: " + url)

            print_url = ""
            if len(events) == 0:
                print_url = "(" + url + ")"
            print(len(events), "scraped from", title, "(" + language + ")", print_url)
            all_events.extend(events)

        count_parsed_events = len(all_events)
        all_events = append_city_and_filter_for_switzerland(all_events, args.debug)
        count_swiss_events = len(all_events)
        seen = set()

        def hasNotBeenSeen(event: sheets.Event) -> bool:
            newKey = event.name + event.date.strftime("%x") + event.language
            if newKey in seen:
                print("Removing duplicate event:", event)
                return False
            seen.add(newKey)
            return True

        all_events = list(filter(hasNotBeenSeen, all_events))
        print("Removed", count_swiss_events - len(all_events), "duplicated event(s)")

        for event in all_events:
            # event must have a valid URL
            if not event.url or not (
                event.url.startswith("http://")
                or event.url.startswith("https://")
                or event.url.startswith("mailto:")
            ):
                raise Exception("Invalid URL in event", event)

        with open(args.events_js, "w") as f:
            template = env.get_template("events.js")
            print(
                template.render(
                    {
                        "eventsAsJSON": json.dumps(
                            write_events_as_json(all_events), indent=4
                        ),
                    }
                ),
                file=f,
            )
        print(
            "Wrote",
            len(all_events),
            "events to",
            args.main_html,
            "after parsing",
            count_parsed_events,
            "events from",
            len(calendars),
            "calendars.",
        )

    if args.main_html:
        with open(args.main_html, "w") as f:
            template = env.get_template("index.html")
            print(
                template.render(
                    {
                        "languageStrings": json.dumps(
                            sheets.get_language_strings("MainPage", "A1:D50"), indent=4
                        ),
                        "initialDate": format_date(today, "MM/dd/yyyy", locale="en"),
                        "initialTime": str(
                            math.floor(
                                datetime.datetime.timestamp(datetime.datetime.now())
                            )
                        ),
                    }
                ),
                file=f,
            )

    if args.about_prefix:
        calendarList = []
        for calendar in calendars:
            calendarList.append('<a href="' + calendar[3] + '">' + calendar[0] + "</a>")
        languageStrings = sheets.get_language_strings("AboutPage", "A1:C4")
        for languageCode in ["en", "fr"]:
            transposed = {}
            for d in languageStrings:
                transposed[d["id"]] = d[languageCode]
            languageSuffix = "_" + languageCode + ".html"
            with open(args.about_prefix + languageSuffix, "w") as f:
                template = env.get_template("about" + languageSuffix)
                print(
                    template.render(
                        {
                            "backText": transposed["backText"],
                            "languageCode": languageCode,
                            "mainTitle": transposed["mainTitle"],
                            "calendarList": ", ".join(calendarList),
                        }
                    ),
                    file=f,
                )


if __name__ == "__main__":
    main()
