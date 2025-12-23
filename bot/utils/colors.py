"""
ANSI Color Codes for Terminal Output
"""

class Colors:
    """ANSI color codes for terminal output"""
    
    # Basic colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    
    # Reset
    RESET = '\033[0m'
    
    @staticmethod
    def colorize(text: str, color: str, bold: bool = False) -> str:
        """Wrap text in color codes"""
        prefix = f"{Colors.BOLD}{color}" if bold else color
        return f"{prefix}{text}{Colors.RESET}"
    
    @staticmethod
    def success(text: str) -> str:
        """Green text for success messages"""
        return Colors.colorize(text, Colors.BRIGHT_GREEN)
    
    @staticmethod
    def error(text: str) -> str:
        """Red text for error messages"""
        return Colors.colorize(text, Colors.BRIGHT_RED)
    
    @staticmethod
    def warning(text: str) -> str:
        """Yellow text for warning messages"""
        return Colors.colorize(text, Colors.BRIGHT_YELLOW)
    
    @staticmethod
    def info(text: str) -> str:
        """Cyan text for info messages"""
        return Colors.colorize(text, Colors.BRIGHT_CYAN)
    
    @staticmethod
    def price_up(text: str) -> str:
        """Green text for price increases"""
        return Colors.colorize(text, Colors.GREEN)
    
    @staticmethod
    def price_down(text: str) -> str:
        """Red text for price decreases"""
        return Colors.colorize(text, Colors.RED)
    
    @staticmethod
    def money_positive(text: str) -> str:
        """Green text for positive money values"""
        return Colors.colorize(text, Colors.BRIGHT_GREEN, bold=True)
    
    @staticmethod
    def money_negative(text: str) -> str:
        """Red text for negative money values"""
        return Colors.colorize(text, Colors.BRIGHT_RED, bold=True)
