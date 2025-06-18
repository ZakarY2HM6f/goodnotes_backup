from pathlib import Path
from os import path
import requests
from collections import OrderedDict
import json
import re
import time

from selenium import webdriver
from selenium.webdriver import ActionChains, ChromeOptions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

import tkinter
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import StringVar

# Constants
notes_locator = (By.CSS_SELECTOR, "div.bxEQIA")
folders_locator = (By.CSS_SELECTOR, "div.jVVdlL")
title_locator = (By.CSS_SELECTOR, "p.jyOVsa.free")
dropdown_locator = (By.CSS_SELECTOR, "svg#libraryDocumentNameChevronId")
popup_locator = (By.CSS_SELECTOR, "div#menuPopoverOverlay")
export_locator = (By.CSS_SELECTOR, "button#exportPdfButton")
spy_locator = (By.TAG_NAME, "selenium-data")
back_locator = (By.CSS_SELECTOR, "button#libraryBreadcrumbsBackButton")

cookies_path = Path(__file__).parent.joinpath(".cookies.json")
config_path = Path(__file__).parent.joinpath(".config.json")
download_path = Path(__file__).parent.joinpath("download_hook.js")

# Globals
driver = None
tk = None
dest_entry = None
progress = None


def pick_dest():
    dest_path = filedialog.askdirectory()
    dest_entry.delete(0, "end")
    dest_entry.insert(0, dest_path)


class element_content_changed:
    def __init__(self, element):
        try:
            self.element = element
            self.innerHTML = element.get_attribute("innerHTML")
        except:
            pass

    def __call__(self, _):
        try:
            new_innerHTML = self.element.get_attribute("innerHTML")
            assert self.innerHTML == new_innerHTML
        except:
            return True
        return False


def download(url, filepath):
    # print(f"downloading\nfrom: {url}\nto: {filepath}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def backup():
    dest_path = Path(dest_entry.get())
    try:
        dest_path = dest_path.resolve(strict=True)
        driver.find_element(By.ID, "libraryTopbarTitle-0")
    except FileNotFoundError:
        print("backup path invalid")
        messagebox.showinfo(
            "Backup Path Invalid",
            "Please set the backup folder first.",
        )
        return
    except NoSuchElementException:
        print("user not logged in")
        messagebox.showinfo(
            "Not Logged In",
            "Please login first.",
        )
        return

    progress.start()
    print("starting backup")

    with open(download_path, "r") as f:
        js = f.read()
        driver.execute_script(js)

    current = OrderedDict({"root": dest_path})
    traversed = set()
    while current:
        try:
            gallery_elm = driver.find_element(By.ID, "libraryViewDocumentGrid")
            note_elms = gallery_elm.find_elements(*notes_locator)
            folder_elms = gallery_elm.find_elements(*folders_locator)
        except:
            note_elms = []
            folder_elms = []

        for note_elm in note_elms:
            note_elm = note_elm.find_element(By.XPATH, "./div")
            note_id = note_elm.get_attribute("id")

            if note_id in traversed:
                print("traverse repeated: ", note_id)
                continue

            title_elm = note_elm.find_element(*title_locator)
            title = title_elm.text

            dropdown_elm = note_elm.find_element(*dropdown_locator)
            ac = ActionChains(driver)
            ac.move_to_element(dropdown_elm)
            ac.click()
            ac.perform()

            popup_elm = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(popup_locator)
            )
            export_btn = popup_elm.find_element(*export_locator)
            ac = ActionChains(driver)
            ac.move_to_element(export_btn)
            ac.click()
            ac.perform()

            a_elem = WebDriverWait(driver, 500).until(
                EC.presence_of_element_located(spy_locator)
            )
            href = a_elem.get_attribute("href")
            dest = path.join(*current.values(), f"{title}.pdf")
            download(href, dest)

            driver.execute_script("arguments[0].remove()", a_elem)
            traversed.add(note_id)
            print("just traversed: ", note_id)
            print("total traversed: ", traversed)

            time.sleep(0.1)

        folder_elm = next(
            (e for e in folder_elms if e.get_attribute("id") not in traversed), None
        )

        if folder_elm:
            title_elm = folder_elm.find_element(*title_locator)
            title = title_elm.text

            folder_id = folder_elm.get_attribute("id")
            current[folder_id] = title
            print(f"traversing {folder_id}")
            Path(path.join(*current.values())).mkdir(parents=True, exist_ok=True)

            ac = ActionChains(driver)
            ac.move_to_element(folder_elm)
            ac.click()
            ac.perform()
            WebDriverWait(driver, 10).until(element_content_changed(gallery_elm))
        else:
            id, _ = current.popitem()

            try:
                back_btn = driver.find_element(*back_locator)
                ac = ActionChains(driver)
                ac.move_to_element(back_btn)
                ac.click()
                ac.perform()
                WebDriverWait(driver, 10).until(element_content_changed(gallery_elm))
            except:
                pass

            traversed.add(id)
            print("just traversed: ", id)
            print("total traversed: ", traversed)

        time.sleep(0.1)

    print("backup finished")
    progress.stop()


def load_cookies():
    with open(cookies_path, "r") as f:
        cookies = f.read()
        if cookies:
            cookies = json.loads(cookies)
        if isinstance(cookies, list):
            for c in cookies:
                driver.add_cookie(c)

    driver.refresh()


def save_cookies():
    s = driver.get_cookies()
    if s:
        with open(cookies_path, "w") as f:
            json.dump(s, f)


def save_config(_, __, ___):
    config = {"dest_path": dest_entry.get()}
    with open(config_path, "w") as f:
        json.dump(config, f)


def main():
    global driver
    options = ChromeOptions()
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_path),
            "download.prompt_for_download": False,
            "download_restrictions": 3,
        },
    )
    driver = webdriver.Chrome(options)

    driver.get("https://web.goodnotes.com/home")
    load_cookies()

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            dest_path = config["dest_path"]
    except:
        dest_path = ""

    # GUI
    global tk
    global dest_entry
    global progress
    tk = tkinter.Tk()
    tk.title("GoodNotes Backup")
    tk.geometry("300x150")

    dest_lbl = ttk.Label(tk, text="Backup Folder: ")
    dest_var = StringVar(tk, dest_path)
    dest_var.trace_add("write", save_config)
    dest_entry = ttk.Entry(tk, textvariable=dest_var)
    dest_btn = ttk.Button(tk, text="Browse", command=pick_dest)

    backup_btn = ttk.Button(tk, text="Backup Now", command=backup)
    progress = ttk.Progressbar(tk, mode="indeterminate")

    style = {"fill": "x", "padx": 10, "pady": 2}

    dest_lbl.pack(**style)
    dest_entry.pack(**style)
    dest_btn.pack(**style)

    ttk.Separator(tk, orient="horizontal").pack()

    backup_btn.pack(**style)
    progress.pack(**style)

    tk.mainloop()

    save_cookies()
    driver.quit()


if __name__ == "__main__":
    main()
