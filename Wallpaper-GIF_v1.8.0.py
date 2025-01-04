import ctypes
import time
import threading
import os
import json
from tkinter import Tk, filedialog, Button, Label
from PIL import Image, ImageSequence, ImageDraw
from pystray import Icon, Menu, MenuItem
from pygetwindow import getActiveWindow
from pygame import mixer
from functools import partial

# Глобальные переменные
is_paused = False
is_running = True
is_music_paused = False
current_gif_path = None
current_music_path = None
icon = None
volume_level = 50
presets_file = "presets.json"
temp_frame_path = os.path.join(os.getcwd(), "wallpaper_frame.bmp")  # Локальная папка для BMP

# Инициализация аудио библиотеки
mixer.init()

def set_wallpaper(image_path):
    ctypes.windll.user32.SystemParametersInfoW(20, 0, image_path, 0)

def wait_for_file(path, timeout=2):
    """Ожидает, пока файл станет доступен"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not os.path.exists(path):
            return True
        try:
            os.remove(path)
            return True
        except PermissionError:
            time.sleep(0.1)
    return False

def animate_gif_as_wallpaper(gif_path):
    global is_paused, is_running
    try:
        gif = Image.open(gif_path)
        while is_running:
            for frame in ImageSequence.Iterator(gif):
                if not is_running:
                    break
                if not is_paused:
                    try:
                        # Ждем, пока файл освободится
                        if not wait_for_file(temp_frame_path):
                            print("Не удалось получить доступ к временному файлу. Пропускаем кадр.")
                            continue

                        # Сохраняем кадр безопасно
                        with open(temp_frame_path, "wb") as temp_file:
                            frame.convert("RGB").save(temp_file, format="BMP")

                        set_wallpaper(temp_frame_path)
                        time.sleep(gif.info.get('duration', 100) / 1000.0)
                    except Exception as e:
                        print(f"Ошибка при обработке кадра: {e}")
    except Exception as e:
        print(f"Ошибка: {e}")

def select_image():
    global current_gif_path, is_running
    file_path = filedialog.askopenfilename(filetypes=[("GIF files", "*.gif")])
    if file_path:
        current_gif_path = file_path
        is_running = True
        threading.Thread(target=animate_gif_as_wallpaper, args=(file_path,), daemon=True).start()

def select_music():
    global current_music_path
    file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav")])
    if file_path:
        current_music_path = file_path
        mixer.music.load(file_path)
        mixer.music.play(-1)
        mixer.music.set_volume(volume_level / 100)
        update_menu()  # Обновляем меню сразу после запуска музыки

def toggle_pause_music(icon, item):
    global is_music_paused
    if is_music_paused:
        mixer.music.unpause()
    else:
        mixer.music.pause()
    is_music_paused = not is_music_paused
    update_menu()

def set_volume(icon, level, *args):
    global volume_level
    volume_level = level
    mixer.music.set_volume(volume_level / 100)
    update_menu()  # Обновляем меню после изменения громкости

def save_preset():
    global current_gif_path, current_music_path
    preset_name = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if preset_name:
        preset_data = {
            "gif": current_gif_path,
            "music": current_music_path,
            "volume": volume_level
        }
        with open(preset_name, "w", encoding="utf-8") as f:
            json.dump(preset_data, f, ensure_ascii=False, indent=4)

def load_preset():
    global current_gif_path, current_music_path, volume_level
    preset_file = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if preset_file:
        with open(preset_file, "r", encoding="utf-8") as f:
            preset_data = json.load(f)
        current_gif_path = preset_data.get("gif")
        current_music_path = preset_data.get("music")
        volume_level = preset_data.get("volume", 50)

        if current_gif_path:
            threading.Thread(target=animate_gif_as_wallpaper, args=(current_gif_path,), daemon=True).start()

        if current_music_path:
            mixer.music.load(current_music_path)
            mixer.music.play(-1)
            mixer.music.set_volume(volume_level / 100)
            update_menu()  # Обновляем меню сразу после загрузки пресета

def update_menu():
    global icon
    icon.menu = Menu(
        MenuItem("Возобновить" if is_paused else "Пауза", toggle_pause),
        MenuItem("Воспроизвести Музыку" if is_music_paused else "Пауза Музыки", toggle_pause_music),
        MenuItem("Громкость", Menu(
            *(MenuItem(f"{i}%", partial(set_volume, None, i)) for i in range(0, 101, 5))  # Добавляем 5% громкости
        )),
        MenuItem("Показать Главное Меню", show_main_menu, enabled=is_running),  # Кнопка для показа главного меню
        MenuItem("Выход", exit_app)
    )

def show_main_menu(icon, item):
    global is_running
    is_running = True
    create_gui()  # Показать главное меню
    update_menu()  # Обновить меню после показа главного окна

def toggle_pause(icon, item):
    global is_paused
    is_paused = not is_paused
    update_menu()  # Пересоздаем меню с обновленным текстом

def exit_app(icon, item):
    global is_running
    is_running = False
    mixer.music.stop()
    icon.stop()

def create_image():
    """Создает простой значок для системного трея"""
    image = Image.new('RGB', (64, 64), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 16, 48, 48], fill=(0, 0, 255))
    return image

def create_tray_icon():
    global icon
    menu = Menu(
        MenuItem("Пауза", toggle_pause),
        MenuItem("Пауза Музыки", toggle_pause_music),
        MenuItem("Выход", exit_app)
    )
    icon = Icon("GIF Wallpaper", create_image(), "GIF Wallpaper Manager", menu)
    threading.Thread(target=icon.run, daemon=True).start()

def create_gui():
    root = Tk()
    root.title("GIF Wallpaper Manager")
    root.geometry("300x250")

    Label(root, text="Выберите GIF файл для обоев").pack(pady=10)
    Button(root, text="Выбрать GIF", command=select_image).pack(pady=5)

    Label(root, text="Выберите аудио файл для воспроизведения").pack(pady=10)
    Button(root, text="Выбрать Музыку", command=select_music).pack(pady=5)

    Button(root, text="Сохранить Пресет", command=save_preset).pack(pady=5)
    Button(root, text="Загрузить Пресет", command=load_preset).pack(pady=5)

    def minimize_to_tray():
        window = getActiveWindow()
        if window:
            window.minimize()
        root.withdraw()

    Button(root, text="Свернуть в трей", command=minimize_to_tray).pack(pady=5)

    root.protocol("WM_DELETE_WINDOW", minimize_to_tray)
    root.mainloop()

if __name__ == "__main__":
    threading.Thread(target=create_tray_icon, daemon=True).start()
    create_gui()
