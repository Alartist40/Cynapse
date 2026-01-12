import os

def create_icon_placeholder():
    """Create assets folder - icon is optional"""
    print("📁 Creating assets directory...")
    if not os.path.exists('assets'):
        os.makedirs('assets')
    print("✅ Assets directory ready")
    print("💡 Note: You can add a custom 'icon.ico' file to the assets folder later")

if __name__ == "__main__":
    create_icon_placeholder()