function changeLanguage(lang, refresh = true) {
    currentLanguage = lang;
    if (lang == "fr") {
        currentRegions = new Set([ "Romandie" ]);
        currentOrganizations = new Set([ "FZC", "OPF" ]);
    } else {
        currentRegions = new Set([ "Deutschschweiz" ]);
        currentOrganizations = new Set();
    }
    if (lang == "fr" || (lang = "de")) {
        currentLocale = lang + "-CH";
    } else {
        currentLocale = "en-GB";
    }
    if (refresh) {
        refreshAll();
    }
}

function refreshAll() {
    for (let i in languageStrings) {
        let d = languageStrings.at(i);
        document.getElementById(d.id).innerHTML = d[currentLanguage];
    }
    const collection = document.getElementsByClassName("LanguageFlag");
    for (let i = 0; i < collection.length; i++) {
        e = collection[i];
        if (e.id == "Flag-" + currentLanguage) {
            e.classList.add("Highlighted");
        } else {
            e.classList.remove("Highlighted");
        }
    }
    e = document.getElementById("AboutText");
    if (currentLanguage == "fr") {
        e.href = "about_fr.html";
    } else {
        e.href = "about_en.html";
    }
    rebuildEventTable(currentRegions, currentLocale, currentOrganizations);
    updateFilterButtons();
}

function updateDateDiff() {
    let inputInitialDate = document.getElementById("initialDate").innerHTML;
    const initialDate = new Date(inputInitialDate);
    let inputInitialTime = document.getElementById("initialTime").innerHTML;
    const initialTime = new Date(parseInt(inputInitialTime) * 1e3);
    var diffTime = Math.abs(nowDate - initialTime);
    var diffMinutes = Math.floor(diffTime / (60 * 1e3));
    if (diffMinutes < 2) {
        t = "à l'instant";
    } else if (diffMinutes < 60) {
        t = "il y a " + diffMinutes + " minutes";
    } else {
        var diffHours = Math.floor(diffMinutes / 60);
        if (diffHours == 1) {
            t = "il y a une heure";
        } else if (diffHours < 24) {
            t = "il y a " + diffHours + " heures";
        } else {
            var diffDays = Math.floor(diffHours / 24);
            if (diffDays == 1) {
                t = "hier";
            } else {
                t = "il y a " + diffDays + " jours";
            }
        }
    }
    document.getElementById("dateDiffHere").innerHTML = t;
}

const nowDate = new Date();

let today = nowDate.setHours(0, 0, 0, 0);

function displayDate(then, date_string) {
    let diff = (then - today) / (1e3 * 60 * 60 * 24);
    if (diff == 0) {
        const d = {
            "de-CH": "heute",
            "en-GB": "today",
            "fr-CH": "aujourd'hui"
        };
        return d[locale];
    } else if (diff == 1) {
        const d = {
            "de-CH": "morgen",
            "en-GB": "tomorrow",
            "fr-CH": "demain"
        };
        return d[locale];
    } else if (diff < 7) {
        let d = {
            "de-CH": `in ${diff} Tage`,
            "en-GB": `in ${diff} days`,
            "fr-CH": `dans ${diff} jours`
        };
        return d[locale];
    } else {
        return date_string;
    }
}

function injectTable(events, locale) {
    let t = "";
    events.sort(function(a, b) {
        return a.date - b.date;
    });
    for (let x in events) {
        let event = events[x];
        workshopSuffix = "";
        if (event.organizer == "FZC" || event.organizer == "OPF") {
            let prefix = "Organized by";
            let organizer = "One Planet Friends";
            if (locale == "fr-CH") {
                prefix = "Organisé par";
                organizer = "Fresques Zamies & Co";
            } else if (locale == "de-CH") {
                prefix = "Veranstaltet von";
            }
            workshopSuffix = "<span class='w3-animate-fading OrgOPFByline'><br>" + prefix + " <b>" + organizer + "</b></span>";
        }
        t += '<tr class="WorkflowRow" onclick="navigate(this, \'' + event.url + "')\">";
        t += "<td>" + event.title + ' <img src="./flags/icons8-' + event.language + '-16.png" alt="' + event.language + '">' + workshopSuffix + "</td>";
        let then = new Date(event.date * 1e3);
        t += '<td class="EventLongDate">' + displayDate(then, then.toLocaleString(locale, {
            dateStyle: "full"
        })) + "</td>";
        t += '<td class="EventShortDate removed">' + then.toLocaleString(locale, {
            dateStyle: "short"
        }) + "</td>";
        t += '<td class="eventLocation">' + event.city + '<span class="EventLocationDetails hidden"><br>' + event.place + "</span></td>";
        t += "</tr>";
    }
    return t;
}

function rebuildEventTable(regions, locale, organizers) {
    function eventIsInTheFuture(event) {
        return event.date * 1e3 >= today;
    }
    let filtered = events.filter(eventIsInTheFuture);
    function organizerIsAllowed(event) {
        return organizers == null || organizers.size == 0 || organizers.has(event.organizer);
    }
    filtered = filtered.filter(organizerIsAllowed);
    function regionIsAllowed(event) {
        return event.lregion == "Both" || regions.has(event.lregion);
    }
    filtered = filtered.filter(regionIsAllowed);
    document.getElementById("event_container").innerHTML = injectTable(filtered, locale);
}

function navigate(t, url) {
    t.style.cursor = "wait";
    window.location = url;
}

currentLanguage = "en";

currentLocale = "en-GB";

currentRegions = new Set([ "Deutschschweiz" ]);

currentOrganizations = new Set();

function handleSearchParams() {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    let lang = urlParams.get("lang");
    if (lang !== null) {
        changeLanguage(lang, false);
    }
}

function ensureClassOnElementId(id, ensure, c) {
    e = document.getElementById(id);
    if (e == null) {
        return;
    }
    if (ensure) {
        e.classList.add(c);
    } else {
        e.classList.remove(c);
    }
}

function clickFilterRegionRomandie() {
    if (currentRegions.has("Romandie") && currentRegions.size > 1) {
        currentRegions.delete("Romandie");
    } else {
        currentRegions.add("Romandie");
    }
    refreshAll();
}

function clickFilterRegionDeutschschweiz() {
    if (currentRegions.has("Deutschschweiz") && currentRegions.size > 1) {
        currentRegions.delete("Deutschschweiz");
    } else {
        currentRegions.add("Deutschschweiz");
    }
    refreshAll();
}

function clickFilterOrgOPF() {
    currentOrganizations = new Set([ "FZC", "OPF" ]);
    refreshAll();
}

function clickFilterOrgCF() {
    if (currentOrganizations.has("CF") && currentOrganizations.size > 1) {
        currentOrganizations.delete("CF");
    } else {
        currentOrganizations.add("CF");
    }
    refreshAll();
}

function clickFilterOrgAll() {
    currentOrganizations = new Set();
    refreshAll();
}

function updateFilterButtons() {
    ensureClassOnElementId("FilterRegionRomandie", currentRegions.has("Romandie"), "FilterButtonHighlighted");
    ensureClassOnElementId("FilterRegionDeutschschweiz", currentRegions.has("Deutschschweiz"), "FilterButtonHighlighted");
    ensureClassOnElementId("FilterOrgOPF", currentOrganizations !== null && currentOrganizations.has("OPF"), "FilterButtonHighlighted");
    ensureClassOnElementId("FilterOrgCF", currentOrganizations !== null && currentOrganizations.has("CF"), "FilterButtonHighlighted");
    ensureClassOnElementId("FilterOrgAll", currentOrganizations == null || currentOrganizations.size == 0, "FilterButtonHighlighted");
}