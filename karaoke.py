import json
import logging
import os
import random
import socket
import subprocess
import time
import contextlib
import math
from pathlib import Path
from subprocess import CalledProcessError, check_output
import pygame
import qrcode
from unidecode import unidecode
import configparser
import gettext

from collections import *

from lib import omxclient, vlcclient
from lib.get_platform import get_platform

if get_platform() != "windows":
    from signal import SIGALRM, alarm, signal


class Karaoke:

    raspi_wifi_config_ip = "10.0.0.1"
    raspi_wifi_conf_file = "/etc/raspiwifi/raspiwifi.conf"
    raspi_wifi_config_installed = os.path.exists(raspi_wifi_conf_file)

    queue = []
    available_songs = []
    now_playing = None
    now_playing_filename = None
    now_playing_user = None
    now_playing_transpose = 0
    transposing = False
    remove_vocal = False
    is_paused = True
    process = None
    qr_code_path = None
    base_path = os.path.dirname(__file__)
    volume_offset = 0
    loop_interval = 500  # in milliseconds
    default_logo_path = os.path.join(base_path, "logo.png")
    scored = True
    score = None
    critic = None

    def __init__(self, args):

        # override with supplied constructor args if provided
        self.port = args.port
        self.hide_ip = args.hide_ip
        self.hide_raspiwifi_instructions = args.hide_raspiwifi_instructions
        self.hide_splash_screen = args.hide_splash_screen
        self.omxplayer_adev = args.omxplayer_adev
        self.download_path = args.download_path
        self.dual_screen = args.dual_screen
        self.high_quality = args.high_quality
        self.splash_delay = int(args.splash_delay)
        self.volume_offset = self.volume = args.volume
        self.youtubedl_path = args.youtubedl_path
        self.omxplayer_path = args.omxplayer_path
        self.use_omxplayer = args.use_omxplayer
        self.use_vlc = args.use_vlc
        self.vlc_path = args.vlc_path
        self.vlc_port = args.vlc_port
        self.logo_path = (
            self.default_logo_path if args.logo_path == None else args.logo_path
        )
        # self.show_overlay = args.show_overlay
        self.log_level = int(args.log_level)

        # other initializations
        self.platform = get_platform()
        self.vlcclient = None
        self.omxclient = None
        self.screen = None
        self.player_state = {}

        self.config_obj = configparser.ConfigParser()
        # This is for the autostart script to work properly
        if self.platform != "windows":
            # os.chdir(os.path.dirname(sys.argv[0]))
            os.chdir(self.base_path)

        self.config_obj.read("config.ini")
        self.user_lng = self.config_obj.get("USERPREFERENCES", "language")
        self.user_audio_delay = self.config_obj.get("USERPREFERENCES", "audio_delay")
        self.disable_score = (
            args.disable_score if not args.disable_score is None
            else self.config_obj.get("USERPREFERENCES", "disable_score")
        )
        self.disable_bg_music = (
            args.disable_bg_music if not args.disable_bg_music is None
            else self.config_obj.get("USERPREFERENCES", "disable_bg_music")
        )
        self.show_overlay = (
            args.show_overlay if not args.show_overlay is None
            else self.config_obj.get("USERPREFERENCES", "show_overlay")
        )

        trans = gettext.translation(
            "messages", localedir="translations", languages=[self.user_lng]
        )
        trans.install()
        self._ = trans.gettext

        pygame.mixer.init()
        pygame.mixer.music.load("sound-effects/saloon-piano-music.ogg")
        pygame.mixer.music.set_volume(0.2)

        logging.basicConfig(
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=int(self.log_level),
        )

        logging.debug(
            """
    http port: %s
    hide IP: %s
    hide RaspiWiFi instructions: %s,
    hide splash: %s
    splash_delay: %s
    omx audio device: %s
    dual screen: %s
    high quality video: %s
    download path: %s
    default volume: %s
    youtube-dl path: %s
    omxplayer path: %s
    logo path: %s
    Use OMXPlayer: %s
    Use VLC: %s
    VLC path: %s
    VLC port: %s
    log_level: %s
    show overlay: %s
    user pref language: %s
    user pref audio delay: %s
    user pref disable score: %s
    user pref disable background music: %s
    Base Path: %s"""
            % (
                self.port,
                self.hide_ip,
                self.hide_raspiwifi_instructions,
                self.hide_splash_screen,
                self.splash_delay,
                self.omxplayer_adev,
                self.dual_screen,
                self.high_quality,
                self.download_path,
                self.volume_offset,
                self.youtubedl_path,
                self.omxplayer_path,
                self.logo_path,
                self.use_omxplayer,
                self.use_vlc,
                self.vlc_path,
                self.vlc_port,
                self.log_level,
                self.show_overlay,
                self.user_lng,
                self.user_audio_delay,
                self.disable_score,
                self.disable_bg_music,
                self.base_path,
            )
        )

        # Generate connection URL and QR code, retry in case pi is still starting up
        # and doesn't have an IP yet (occurs when launched from /etc/rc.local)
        end_time = int(time.time()) + 30

        if self.platform == "raspberry_pi":
            while int(time.time()) < end_time:
                addresses_str = check_output(["hostname", "-I"]).strip().decode("utf-8")
                addresses = addresses_str.split(" ")
                self.ip = addresses[0]
                if not self.is_network_connected():
                    logging.debug("Couldn't get IP, retrying....")
                else:
                    break
        else:
            self.ip = self.get_ip()

        logging.debug("IP address (for QR code and splash screen): " + self.ip)

        self.url = "http://%s:%s" % (self.ip, self.port)

        # get songs from download_path
        self.get_available_songs()

        self.get_youtubedl_version()

        # clean up old sessions
        self.kill_player()

        self.generate_qr_code()

        if self.use_vlc:
            if not self.show_overlay == str(0):
                self.vlcclient = vlcclient.VLCClient(
                    port=self.vlc_port,
                    path=self.vlc_path,
                    connecttext=self._("Pikaraoke - Connect at: "),
                    qrcode=self.qr_code_path,
                    url=self.url,
                )
            else:
                self.vlcclient = vlcclient.VLCClient(
                    port=self.vlc_port, path=self.vlc_path
                )
        else:
            self.omxclient = omxclient.OMXClient(
                path=self.omxplayer_path,
                adev=self.omxplayer_adev,
                dual_screen=self.dual_screen,
                volume_offset=self.volume_offset,
            )

        if not self.hide_splash_screen:
            self.initialize_screen()
            self.render_splash_screen()

    # Other ip-getting methods are unreliable and sometimes return 127.0.0.1
    # https://stackoverflow.com/a/28950776
    def get_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(("10.255.255.255", 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = "127.0.0.1"
        finally:
            s.close()
        return IP

    def get_raspi_wifi_conf_vals(self):
        """Extract values from the RaspiWiFi configuration file."""
        f = open(self.raspi_wifi_conf_file, "r")

        # Define default values.
        #
        # References:
        # - https://github.com/jasbur/RaspiWiFi/blob/master/initial_setup.py (see defaults in input prompts)
        # - https://github.com/jasbur/RaspiWiFi/blob/master/libs/reset_device/static_files/raspiwifi.conf
        #
        server_port = "80"
        ssid_prefix = "RaspiWiFi Setup"
        ssl_enabled = "0"

        # Override the default values according to the configuration file.
        for line in f.readlines():
            if "server_port=" in line:
                server_port = line.split("t=")[1].strip()
            elif "ssid_prefix=" in line:
                ssid_prefix = line.split("x=")[1].strip()
            elif "ssl_enabled=" in line:
                ssl_enabled = line.split("d=")[1].strip()

        return (server_port, ssid_prefix, ssl_enabled)

    def get_youtubedl_version(self):
        self.youtubedl_version = (
            check_output([self.youtubedl_path, "--version"]).strip().decode("utf8")
        )
        return self.youtubedl_version

    def upgrade_youtubedl(self):
        logging.info(
            "Upgrading youtube-dl, current version: %s" % self.youtubedl_version
        )
        try:
            output = (
                check_output([self.youtubedl_path, "-U"], stderr=subprocess.STDOUT)
                .decode("utf8")
                .strip()
            )
        except CalledProcessError as e:
            output = e.output.decode("utf8")
        logging.info(output)
        if "You installed yt-dlp with pip or using the wheel from PyPi" in output:
            try:
                logging.info("Attempting youtube-dl upgrade via pip3...")
                output = check_output(
                    ["pip3", "install", "--upgrade", "yt-dlp"]
                ).decode("utf8")
            except FileNotFoundError:
                logging.info("Attempting youtube-dl upgrade via pip...")
                output = check_output(["pip", "install", "--upgrade", "yt-dlp"]).decode(
                    "utf8"
                )
            logging.info(output)
        self.get_youtubedl_version()
        logging.info("Done. New version: %s" % self.youtubedl_version)

    def force_audio(self, output):
        logging.debug("Forcing audio output through: " + output)

        try:
            asound = open("/etc/asound.conf", "w+")
            str = (
                "pcm.!default{type hw card "
                + output
                + "} ctl.!default {type hw card "
                + output
                + "}"
            )
            asound.write(str)
            resultado = True
        except Exception as e:
            resultado = False
            logging.debug(e)
        return resultado

    def update_pikaraoke(self):
        logging.debug("Updating system...")

        try:
            import git

            g = git.cmd.Git(self.base_path)
            g.fetch()
            g.reset('--hard')
            g.merge('@{u}')
            resultado = "PiKaraoke successfully updated!"
        except Exception as e:
            resultado = "Error trying to update PiKaraoke"
            logging.debug(e)

        if self.platform == "raspberry_pi":
            os.system("reboot")
        return resultado

    def change_prefs(self, pref, val):
        logging.debug("Changing Preferences")
        userprefs = self.config_obj["USERPREFERENCES"]
        userprefs[pref] = str(val)
        with open("config.ini", "w") as conf:
            self.config_obj.write(conf)
        setattr(self, pref, str(val))

    def is_network_connected(self):
        return not len(self.ip) < 7

    def generate_qr_code(self):
        logging.debug("Generating URL QR code")
        qr = qrcode.QRCode(
            version=1,
            box_size=1,
            border=4,
        )
        qr.add_data(self.url)
        qr.make()
        img = qr.make_image()
        self.qr_code_path = os.path.join(self.base_path, "qrcode.png")
        img.save(self.qr_code_path)

    def get_default_display_mode(self):
        if self.use_vlc:
            if self.platform == "raspberry_pi":
                os.environ[
                    "SDL_VIDEO_CENTERED"
                ] = "1"  # HACK apparently if display mode is fullscreen the vlc window will be at the bottom of pygame
                return pygame.NOFRAME
            else:
                return pygame.FULLSCREEN
        else:
            return pygame.FULLSCREEN

    def initialize_screen(self):
        if not self.hide_splash_screen:
            logging.debug("Initializing pygame")
            self.full_screen = True
            pygame.display.init()
            pygame.display.set_caption("pikaraoke")
            pygame.font.init()
            pygame.mouse.set_visible(0)
            self.width = pygame.display.Info().current_w
            self.height = pygame.display.Info().current_h
            logging.debug("Resolution = " + str(self.width) + "x" + str(self.height))
            font_size = self.width//48
            self.font = pygame.font.SysFont(pygame.font.get_default_font(), font_size)
            # self.width = 800
            # self.height = 600
            logging.debug("Initializing screen mode")
            # if self.platform == "windows":
            #     self.screen = pygame.display.set_mode(
            #         [self.width, self.height], self.get_default_display_mode()
            #     )
            if self.platform == "windows":
                self.screen = pygame.display.set_mode([self.width, self.height])
            else:
                # this section is an unbelievable nasty hack - for some reason Pygame
                # needs a keyboardinterrupt to initialise in some limited circumstances
                # source: https://stackoverflow.com/questions/17035699/pygame-requires-keyboard-interrupt-to-init-display
                class Alarm(Exception):
                    pass

                def alarm_handler(signum, frame):
                    raise Alarm

                signal(SIGALRM, alarm_handler)
                alarm(3)
                try:
                    self.screen = pygame.display.set_mode(
                        [self.width, self.height], self.get_default_display_mode()
                    )
                    alarm(0)
                except Alarm:
                    raise KeyboardInterrupt
            logging.debug("Done initializing splash screen")

    def toggle_full_screen(self):
        if not self.hide_splash_screen:
            logging.debug("Toggling fullscreen...")
            if self.full_screen:
                self.screen = pygame.display.set_mode([1280, 720])
                self.render_splash_screen()
                self.full_screen = False
            else:
                self.screen = pygame.display.set_mode(
                    [self.width, self.height], self.get_default_display_mode()
                )
                self.render_splash_screen()
                self.full_screen = True

    def render_splash_screen(self):
        if not self.hide_splash_screen:
            logging.debug("Rendering splash screen")

            if self.disable_bg_music == str(0):
                if len(self.queue) == 0 and not self.is_file_playing():
                    pygame.mixer.music.play(-1)

            self.screen.fill((18, 0, 20))

            logo_dimension = self.width//4
            logo = pygame.image.load(self.logo_path)
            logo = pygame.transform.scale(logo, (logo_dimension, logo_dimension))
            logo_rect = logo.get_rect(center=self.screen.get_rect().center)
            self.screen.blit(logo, logo_rect)

            #blitY = self.screen.get_rect().bottomleft[1] - 80
            blitY = self.height - self.height // 13
            x_space = self.width//40

            if not self.hide_ip:
                p_dimension = self.width//12
                p_image = pygame.image.load(self.qr_code_path)
                p_image = pygame.transform.scale(p_image, (p_dimension, p_dimension))
                self.screen.blit(p_image, (x_space, blitY - self.height//9))
                if not self.is_network_connected():
                    text = self.font.render(
                        self._("Wifi/Network not connected. Shutting down in 10s..."),
                        True,
                        (255, 255, 255),
                    )
                    self.screen.blit(text, (x_space + p_image.get_width() + 35, blitY))
                    time.sleep(10)
                    logging.info(
                        self._(
                            "No IP found. Network/Wifi configuration required. For wifi config, try: sudo raspi-config or the desktop GUI: startx"
                        )
                    )
                    self.stop()
                else:
                    text = self._("Connect at: ")
                    text = self.font.render(text + self.url, True, (255, 255, 255))
                    self.screen.blit(text, (x_space + p_image.get_width() + 35, blitY))

            if not self.hide_raspiwifi_instructions and (
                self.raspi_wifi_config_installed
                and self.raspi_wifi_config_ip in self.url
            ):
                (
                    server_port,
                    ssid_prefix,
                    ssl_enabled,
                ) = self.get_raspi_wifi_conf_vals()

                text1 = self.font.render(
                    self._("RaspiWifiConfig setup mode detected!"),
                    True,
                    (255, 255, 255),
                )
                text2 = self.font.render(
                    self._("Connect another device/smartphone to the Wifi AP: '%s'")
                    % ssid_prefix,
                    True,
                    (255, 255, 255),
                )
                text3 = self.font.render(
                    self._(
                        "Then point its browser to: '%s://%s%s' and follow the instructions."
                    )
                    % (
                        "https" if ssl_enabled == "1" else "http",
                        self.raspi_wifi_config_ip,
                        ":%s" % server_port if server_port != "80" else "",
                    ),
                    True,
                    (255, 255, 255),
                )
                self.screen.blit(text1, (10, 10))
                self.screen.blit(text2, (10, 50))
                self.screen.blit(text3, (10, 90))

    # Function that scales an image to the full screen
    def transform_scale_keep_ratio(self, image):
        iwidth, iheight = image.get_size()
        scale = min(self.width / iwidth, self.height / iheight)
        new_size = (round(iwidth * scale), round(iheight * scale))
        scaled_image = pygame.transform.smoothscale(image, new_size)
        image_rect = scaled_image.get_rect(center=(self.width // 2, self.height // 2))
        return scaled_image, image_rect

    def refresh_score_screen(self, scaled_bg, bg_rect):

        surface1 = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        surface2 = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        self.screen.blit(scaled_bg, bg_rect)

        your_score_bg_rect_size = [self.width * 0.26, self.height * 0.27]
        critic_bg_rect_size = [self.width * 0.6, self.height * 0.1]

        critic_bg_rect = pygame.Rect(
            self.width / 2 - critic_bg_rect_size[0] / 2,
            self.height * 0.6,
            critic_bg_rect_size[0],
            critic_bg_rect_size[1],
        )

        your_score_bg_rect = pygame.Rect(
            self.width / 2 - your_score_bg_rect_size[0] / 2,
            self.height * 0.18,
            your_score_bg_rect_size[0],
            your_score_bg_rect_size[1],
        )

        pygame.draw.rect(surface1, [255, 255, 255, 200], your_score_bg_rect, 0)
        pygame.draw.rect(surface1, [150, 0, 150], your_score_bg_rect, 5)

        self.screen.blit(surface1, (0, 0))

        your_score_font = pygame.font.Font(
            "FugazOne-Regular.ttf", round(self.width * 0.03)
        )

        score_text = your_score_font.render(
            self._("Your Score"),
            True,
            (150, 0, 150),
        )

        self.screen.blit(
            score_text,
            (
                your_score_bg_rect.centerx - score_text.get_rect().width / 2,
                self.height * 0.2,
            ),
        )

        if self.score != None:
            self.screen.blit(
                self.score,
                (
                    your_score_bg_rect.centerx - self.score.get_rect().width / 2,
                    self.height * 0.27,
                ),
            )
            if self.critic != None:
                pygame.draw.rect(surface2, [255, 255, 255, 200], critic_bg_rect, 0)
                pygame.draw.rect(surface2, [150, 0, 150], critic_bg_rect, 5)
                self.screen.blit(surface2, (0, 0))

                self.screen.blit(
                    self.critic,
                    (
                        critic_bg_rect.centerx - self.critic.get_rect().width / 2,
                        critic_bg_rect.centery - self.critic.get_rect().height / 2,
                    ),
                )

        pygame.display.update()

    def render_score_screen(self):
        if self.disable_score == str(0):
            logging.debug("Rendering score screen")

            background = pygame.image.load("stage.jpg").convert()
            scaled_bg, bg_rect = self.transform_scale_keep_ratio(background)

            score_number_font = pygame.font.Font(
                "FugazOne-Regular.ttf", round(self.width * 0.064)
            )
            critic_text_font = pygame.font.Font(
                "FugazOne-Regular.ttf", round(self.width * 0.018)
            )

            self.refresh_score_screen(scaled_bg, bg_rect)

            score_sound1 = pygame.mixer.Sound("sound-effects/score1.ogg")
            score_sound1.set_volume(0.2)
            score_sound2 = pygame.mixer.Sound("sound-effects/score2.ogg")
            score_sound2.set_volume(0.2)
            channel = score_sound1.play()

            scoreNum = str(math.ceil(random.triangular(0, 100, 99))).zfill(2)

            if int(scoreNum) < 30:
                sel_color = (255, 50, 50)
                applause = pygame.mixer.Sound("sound-effects/applause-l.ogg")
                critic = [
                    self._("Never sing again... ever."),
                    self._("I hope you don't do this for a living."),
                    self._("Thank god it's over."),
                    self._("Pass the mic for someone else, please!"),
                ]
            elif int(scoreNum) >= 30 and int(scoreNum) < 60:
                sel_color = (255, 200, 50)
                applause = pygame.mixer.Sound("sound-effects/applause-m.ogg")
                critic = [
                    self._("I've seen better singers."),
                    self._("Ok... just ok."),
                    self._("Not bad for a beginner."),
                    self._("You put up a nice show."),
                ]
            else:
                sel_color = (50, 150, 255)
                applause = pygame.mixer.Sound("sound-effects/applause-h.ogg")
                critic = [
                    self._("Congratulations! Couldn't be better."),
                    self._("Wow, have you tried The Voice?"),
                    self._("Please, sing another one!"),
                    self._("You rock! You know that?!"),
                    self._("I wish more people could sing like this."),
                ]

            while channel.get_busy():
                scoreRnd = str(random.randint(0, 99)).zfill(2)
                self.score = score_number_font.render(
                    scoreRnd,
                    True,
                    (150, 0, 150),
                )
                self.refresh_score_screen(scaled_bg, bg_rect)
                pygame.time.wait(100)

            score_sound2.play()

            self.score = score_number_font.render(
                scoreNum,
                True,
                sel_color,
            )

            self.critic = critic_text_font.render(
                random.choice(critic), True, (150, 0, 150)
            )
            self.refresh_score_screen(scaled_bg, bg_rect)

            applause.play()

            pygame.time.wait(5000)

            self.score = None
            self.critic = None

        self.render_splash_screen()

    def render_next_song_to_splash_screen(self):
        if not self.hide_splash_screen:
            self.render_splash_screen()
            if len(self.queue) >= 1:
                logging.debug("Rendering next song to splash screen")
                next_song = self.queue[0]["title"]
                max_length = 60
                if len(next_song) > max_length:
                    next_song = next_song[0:max_length] + "..."
                next_user = self.queue[0]["user"]
                font_next_song = pygame.font.SysFont(pygame.font.get_default_font(), self.width//32)
                text = font_next_song.render(
                    self._("Up next: ") + "%s" % (unidecode(next_song)),
                    True,
                    (0, 128, 0),
                )
                up_next = font_next_song.render(
                    self._("Up next:  "), True, (255, 255, 0)
                )
                font_user_name = pygame.font.SysFont(pygame.font.get_default_font(), self.width//38)
                user_name = font_user_name.render(
                    self._("Added by: ") + "%s" % next_user, True, (255, 120, 0)
                )
                x = self.width - text.get_width() - self.width // 32
                y = self.height // 27
                self.screen.blit(text, (x, y))
                self.screen.blit(up_next, (x, y))
                self.screen.blit(
                    user_name, (self.width - user_name.get_width() - self.width // 32, y + self.width//38)
                )
                return True
            else:
                logging.debug("Could not render next song to splash. No song in queue")
                return False

    def get_search_results(self, textToSearch):
        logging.info("Searching YouTube for: " + textToSearch)
        num_results = 10
        yt_search = 'ytsearch%d:"%s"' % (num_results, unidecode(textToSearch))
        cmd = [self.youtubedl_path, "-j", "--no-playlist", "--flat-playlist", yt_search]
        logging.debug("Youtube-dl search command: " + " ".join(cmd))
        try:
            output = subprocess.check_output(cmd).decode("utf-8")
            logging.debug("Search results: " + output)
            rc = []
            for each in output.split("\n"):
                if len(each) > 2:
                    j = json.loads(each)
                    if (not "title" in j) or (not "url" in j):
                        continue
                    rc.append([j["title"], j["url"], j["id"]])
            return rc
        except Exception as e:
            logging.debug("Error while executing search: " + str(e))
            raise e

    def get_karaoke_search_results(self, songTitle):
        return self.get_search_results(songTitle + " karaoke")

    def download_video(self, video_url, enqueue=False, user="Pikaraoke"):
        logging.info("Downloading video: " + video_url)
        dl_path = self.download_path + "%(title)s---%(id)s.%(ext)s"
        file_quality = (
            "bestvideo[ext!=webm][height<=1080]+bestaudio[ext!=webm]/best[ext!=webm]"
            if self.high_quality
            else "mp4"
        )
        cmd = [self.youtubedl_path, "-f", file_quality, "-o", dl_path, video_url]
        logging.debug("Youtube-dl command: " + " ".join(cmd))
        rc = subprocess.call(cmd)
        if rc != 0:
            logging.error("Error code while downloading, retrying once...")
            rc = subprocess.call(cmd)  # retry once. Seems like this can be flaky
        if rc == 0:
            logging.debug("Song successfully downloaded: " + video_url)
            self.get_available_songs()
            if enqueue:
                y = self.get_youtube_id_from_url(video_url)
                s = self.find_song_by_youtube_id(y)
                if s:
                    self.enqueue(s, user)
                else:
                    logging.error("Error queueing song: " + video_url)
        else:
            logging.error("Error downloading song: " + video_url)
        return rc

    def get_available_songs(self):
        logging.info("Fetching available songs in: " + self.download_path)
        types = [".mp4", ".mp3", ".zip", ".mkv", ".avi", ".webm", ".mov"]
        files_grabbed = []
        P = Path(self.download_path)
        for file in P.rglob("*.*"):
            base, ext = os.path.splitext(file.as_posix())
            if ext.lower() in types:
                if os.path.isfile(file.as_posix()):
                    logging.debug("adding song: " + file.name)
                    files_grabbed.append(file.as_posix())

        self.available_songs = sorted(
            files_grabbed, key=lambda f: str.lower(os.path.basename(f))
        )

    def delete(self, song_path):
        logging.info("Deleting song: " + song_path)
        with contextlib.suppress(FileNotFoundError):
            os.remove(song_path)
        ext = os.path.splitext(song_path)
        # if we have an associated cdg file, delete that too
        cdg_file = song_path.replace(ext[1], ".cdg")
        if os.path.exists(cdg_file):
            os.remove(cdg_file)

        self.get_available_songs()

    def rename(self, song_path, new_name):
        logging.info("Renaming song: '" + song_path + "' to: " + new_name)
        ext = os.path.splitext(song_path)
        if len(ext) == 2:
            new_file_name = new_name + ext[1]
        os.rename(song_path, self.download_path + new_file_name)
        # if we have an associated cdg file, rename that too
        cdg_file = song_path.replace(ext[1], ".cdg")
        if os.path.exists(cdg_file):
            os.rename(cdg_file, self.download_path + new_name + ".cdg")
        self.get_available_songs()

    def filename_from_path(self, file_path):
        rc = os.path.basename(file_path)
        rc = os.path.splitext(rc)[0]
        rc = rc.split("---")[0]  # removes youtube id if present
        return rc

    def find_song_by_youtube_id(self, youtube_id):
        for each in self.available_songs:
            if youtube_id in each:
                return each
        logging.error("No available song found with youtube id: " + youtube_id)
        return None

    def get_youtube_id_from_url(self, url):
        s = url.split("watch?v=")
        if len(s) == 2:
            return s[1]
        else:
            logging.error("Error parsing youtube id from url: " + url)
            return None

    def kill_player(self):
        if self.use_vlc:
            logging.debug("Killing old VLC processes")
            if self.vlcclient != None:
                self.vlcclient.kill()
        else:
            if self.omxclient != None:
                self.omxclient.kill()

    def play_file(self, file_path, extra_params=[]):

        self.now_playing = self.filename_from_path(file_path)
        self.now_playing_filename = file_path

        if self.use_vlc:
            logging.info("Playing video in VLC: " + self.now_playing)
            extra_params += [f"--audio-desync={self.user_audio_delay}"]

            if self.now_playing_transpose == 0:
                self.vlcclient.play_file(
                    file_path,
                    self.volume,
                    extra_params,
                )
            else:
                self.vlcclient.play_file_transpose(
                    file_path,
                    self.now_playing_transpose,
                    self.volume,
                    extra_params,
                )
        else:
            logging.info("Playing video in omxplayer: " + self.now_playing)
            self.omxclient.play_file(file_path)

        self.is_paused = False
        self.render_splash_screen()  # remove old previous track

    def transpose_current(self, semitones):
        if self.use_vlc:
            logging.info("Transposing song by %s semitones" % semitones)
            self.now_playing_transpose = semitones
            self.play_file(self.now_playing_filename)
        else:
            logging.error("Not using VLC. Can't transpose track.")

    def remove_current_vocal(self):
        params = []
        if self.use_vlc:
            logging.info("Removing vocal: " + str(not self.remove_vocal))
            self.remove_vocal = not self.remove_vocal
            if self.remove_vocal == True:
                params = ["--audio-filter", "karaoke"]
            self.play_file(self.now_playing_filename, extra_params=params)
        else:
            logging.error("Not using VLC. Can't remove vocals")

    def set_audio_delay(self, delay=0):

        delay = str(int(self.user_audio_delay) + delay)
        logging.debug("Setting an audio delay of " + delay + " on current video")
        if self.is_file_playing():
            logging.debug("Está tocando, então, altera o video atual")
            if self.use_vlc:
                status_xml = (
                    self.vlcclient.command().text
                    if self.is_paused
                    else self.vlcclient.pause(False).text
                )
                info = self.vlcclient.get_info_xml(status_xml)
                posi = info["position"] * info["length"]
                logging.debug("Posição atual: " + str(posi))
                logging.debug("Filename atual: " + str(self.now_playing_filename))
                self.play_file(
                    self.now_playing_filename,
                    [f"--start-time={posi}"]
                    + (["--start-paused"] if self.is_paused else []),
                )

            else:
                logging.warning("OMXplayer cannot set audio delay!")
            return delay
        logging.warning(
            "Tried to set audio delay on a playing file, but no file is playing!"
        )
        return False

    def is_file_playing(self):
        if self.use_vlc:
            if self.vlcclient != None and self.vlcclient.is_running():
                return True
            else:
                self.now_playing = None
                return False
        else:
            if self.omxclient != None and self.omxclient.is_running():
                return True
            else:
                self.now_playing = None
                return False

    def is_song_in_queue(self, song_path):
        for each in self.queue:
            if each["file"] == song_path:
                return True
        return False

    def enqueue(self, song_path, user="Pikaraoke"):
        if self.is_song_in_queue(song_path):
            logging.warn("Song is already in queue, will not add: " + song_path)
            return False
        else:
            logging.info("'%s' is adding song to queue: %s" % (user, song_path))
            self.queue.append(
                {
                    "user": user,
                    "file": song_path,
                    "title": self.filename_from_path(song_path),
                }
            )
            return True

    def queue_add_random(self, amount):
        logging.info("Adding %d random songs to queue" % amount)
        songs = list(self.available_songs)  # make a copy
        if len(songs) == 0:
            logging.warn("No available songs!")
            return False
        i = 0
        while i < amount:
            r = random.randint(0, len(songs) - 1)
            if self.is_song_in_queue(songs[r]):
                logging.warn("Song already in queue, trying another... " + songs[r])
            else:
                self.queue.append(
                    {
                        "user": "Randomizer",
                        "file": songs[r],
                        "title": self.filename_from_path(songs[r]),
                    }
                )
                i += 1
            songs.pop(r)
            if len(songs) == 0:
                logging.warn("Ran out of songs!")
                return False
        return True

    def queue_clear(self):
        logging.info("Clearing queue!")
        self.queue = []
        self.skip()

    def queue_edit(self, song_name, action):
        index = 0
        song = None
        for each in self.queue:
            if song_name in each["file"]:
                song = each
                break
            else:
                index += 1
        if song == None:
            logging.error("Song not found in queue: " + song["file"])
            return False
        if action == "up":
            if index < 1:
                logging.warn("Song is up next, can't bump up in queue: " + song["file"])
                return False
            else:
                logging.info("Bumping song up in queue: " + song["file"])
                del self.queue[index]
                self.queue.insert(index - 1, song)
                return True
        elif action == "down":
            if index == len(self.queue) - 1:
                logging.warn(
                    "Song is already last, can't bump down in queue: " + song["file"]
                )
                return False
            else:
                logging.info("Bumping song down in queue: " + song["file"])
                del self.queue[index]
                self.queue.insert(index + 1, song)
                return True
        elif action == "delete":
            logging.info("Deleting song from queue: " + song["file"])
            del self.queue[index]
            return True
        else:
            logging.error("Unrecognized direction: " + action)
            return False

    def skip(self):
        if self.is_file_playing():
            logging.info("Skipping: " + self.now_playing)
            if self.use_vlc:
                self.vlcclient.stop()
            else:
                self.omxclient.stop()
            self.reset_now_playing()
            return True
        else:
            logging.warning("Tried to skip, but no file is playing!")
            return False

    def pause(self):
        if self.is_file_playing():
            logging.info("Toggling pause: " + self.now_playing)
            if self.use_vlc:
                if self.vlcclient.is_playing():
                    self.vlcclient.pause()
                else:
                    self.vlcclient.play()
            else:
                if self.omxclient.is_playing():
                    self.omxclient.pause()
                else:
                    self.omxclient.play()
            self.is_paused = not self.is_paused
            return True
        else:
            logging.warning("Tried to pause, but no file is playing!")
            return False

    def vol_up(self):
        if self.is_file_playing():
            if self.use_vlc:
                self.vlcclient.vol_up()
            else:
                self.omxclient.vol_up()
            return True
        else:
            logging.warning("Tried to volume up, but no file is playing!")
            return False

    def vol_down(self):
        if self.is_file_playing():
            if self.use_vlc:
                self.vlcclient.vol_down()
            else:
                self.omxclient.vol_down()
            return True
        else:
            logging.warning("Tried to volume down, but no file is playing!")
            return False

    # def get_state(self):
    #     logging.debug("Getting state")
    #     if self.use_vlc and self.vlcclient.is_transposing:
    #         return defaultdict(lambda: None, self.player_state)
    #     if not self.is_file_playing():
    #         self.player_state["now_playing"] = None
    #         return defaultdict(lambda: None, self.player_state)
    #     new_state = (
    #         self.vlcclient.get_info_xml()
    #         if self.use_vlc
    #         else {
    #             "volume": self.omxclient.volume_offset,
    #             "state": ("paused" if self.omxclient.paused else "playing"),
    #         }
    #     )
    #     self.player_state.update(new_state)
    #     return defaultdict(lambda: None, self.player_state)

    def restart(self):
        logging.debug("Restarting")
        if self.is_file_playing():
            if self.use_vlc:
                self.vlcclient.restart()
            else:
                self.omxclient.restart()
            self.is_paused = False
            return True
        else:
            logging.warning("Tried to restart, but no file is playing!")
            return False

    def stop(self):
        logging.debug("Stoping")
        self.running = False

    def handle_run_loop(self):
        if self.hide_splash_screen:
            time.sleep(self.loop_interval / 1000)
        else:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    logging.warn("Window closed: Exiting pikaraoke...")
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        logging.warn("ESC pressed: Exiting pikaraoke...")
                        self.running = False
                    if event.key == pygame.K_f:
                        self.toggle_full_screen()
            pygame.display.update()
            pygame.time.wait(self.loop_interval)

    # Use this to reset the screen in case it loses focus
    # This seems to occur in windows after playing a video
    def pygame_reset_screen(self):
        if self.hide_splash_screen:
            pass
        else:
            logging.debug("Resetting pygame screen...")
            pygame.display.quit()
            self.initialize_screen()
            self.render_splash_screen()

    def reset_now_playing(self):
        logging.debug("Reseting now playing")
        self.now_playing = None
        self.now_playing_filename = None
        self.now_playing_user = None
        self.is_paused = True
        self.now_playing_transpose = 0
        self.remove_vocal = False
        # self.transposing = False

    def change_language(self, language):
        logging.debug("Changing language to: " + str(language))
        userprefs = self.config_obj["USERPREFERENCES"]
        userprefs["language"] = language
        with open("config.ini", "w") as conf:
            self.config_obj.write(conf)
        trans = gettext.translation(
            "messages", localedir="translations", languages=[language]
        )
        trans.install()
        self._ = trans.gettext

        self.render_splash_screen()

    def update_pref_av_delay(self, delay):
        if delay == "d":
            self.user_audio_delay = str(int(self.user_audio_delay) - 100)
        else:
            self.user_audio_delay = str(int(self.user_audio_delay) + 100)

        userprefs = self.config_obj["USERPREFERENCES"]
        userprefs["audio_delay"] = self.user_audio_delay
        with open("config.ini", "w") as conf:
            self.config_obj.write(conf)

        self.set_audio_delay()

        return self.user_audio_delay

    def start_audio_delay_test(self):
        pygame.mixer.music.stop()
        path = "etc/AudioVideoSyncTest.mp4"
        self.play_file(path)

    def run(self):
        logging.info("Starting PiKaraoke!")

        self.running = True
        while self.running:
            try:
                if not self.is_file_playing():
                    if self.scored != True:
                        self.render_score_screen()
                        self.scored = True

                    elif len(self.queue) > 0:
                        self.reset_now_playing()
                        if not pygame.display.get_active():
                            self.pygame_reset_screen()

                        self.render_next_song_to_splash_screen()
                        i = 0
                        while i < (self.splash_delay * 1000):
                            self.handle_run_loop()
                            i += self.loop_interval
                        pygame.mixer.music.stop()
                        self.play_file(self.queue[0]["file"])
                        self.now_playing_user = self.queue[0]["user"]
                        self.scored = False
                        self.queue.pop(0)

                #  if not self.is_file_playing() and self.now_playing != None:
                #      self.reset_now_playing()
                #  if len(self.queue) > 0:
                #      if not self.is_file_playing():
                #          self.reset_now_playing()
                #          if not pygame.display.get_active():
                #              self.pygame_reset_screen()
                #          self.render_next_song_to_splash_screen()
                #          i = 0
                #          while i < (self.splash_delay * 1000):
                #              self.handle_run_loop()
                #              i += self.loop_interval
                #          self.play_file(self.queue[0]["file"])
                #          self.now_playing_user = self.queue[0]["user"]
                #          self.queue.pop(0)
                elif not pygame.display.get_active() and not self.is_file_playing():
                    logging.debug(
                        "Routine: Pygame display innactive and no file playing"
                    )
                    self.pygame_reset_screen()
                self.handle_run_loop()
            except KeyboardInterrupt:
                logging.warn("Keyboard interrupt: Exiting pikaraoke...")
                self.running = False
