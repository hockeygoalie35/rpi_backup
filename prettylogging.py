import logging
from os import path, mkdir


class CustomFormatter(logging.Formatter):
    def __init__(self, logger_name, version, info_color=None):
        fore_colors = {
            'BLACK': '\033[0;30m',
            'LIGHT_BLACK': '\033[30;1m',
            'RED': '\033[0;31m',
            'LIGHT_RED': '\033[1;31m',
            'GREEN': '\033[0;32m',
            'LIGHT_GREEN': '\033[1;32m',
            'YELLOW': '\033[0;33m',
            'LIGHT_YELLOW': '\033[1;33m',
            'BLUE': '\033[0;34m',
            'LIGHT_BLUE': '\033[1;34m',
            'PURPLE': '\033[0;35m',
            'LIGHT_PURPLE': '\033[1;35m',
            'CYAN': '\033[0;36m',
            'LIGHT_CYAN': '\033[1;36m',
            'GREY': '\033[0;37m',
            'LIGHT_GREY': '\033[1;37m',
            'WHITE': '\033[0;97m',
            'LIGHT_WHITE': '\033[1;97m',
            'RESET': "\033[0m"
        }
        back_colors ={
            'BLACK': '\033[0;40m',
            'LIGHT_BLACK': '\033[40;1m',
            'RED': '\033[0;41m',
            'LIGHT_RED': '\033[1;41m',
            'GREEN': '\033[0;42m',
            'LIGHT_GREEN': '\033[1;42m',
            'YELLOW': '\033[0;43m',
            'LIGHT_YELLOW': '\033[1;43m',
            'BLUE': '\033[0;44m',
            'LIGHT_BLUE': '\033[1;44m',
            'PURPLE': '\033[0;45m',
            'LIGHT_PURPLE': '\033[1;45m',
            'CYAN': '\033[0;46m',
            'LIGHT_CYAN': '\033[1;46m',
            'WHITE': '\033[0;47m',
            'LIGHT_WHITE': '\033[1;47m',
            'RESET': "\033[0m"
        }

        if info_color is None:
            info_color = fore_colors["RESET"]
        else:
            info_color = fore_colors[info_color]

        format = f'%(asctime)s :: {logger_name} :: {version} :: %(levelname)s :: '
        datefmt = '%Y-%m-%d %H:%M:%s'

        self.FORMATS = {
            logging.DEBUG:  format + fore_colors['CYAN'] + '%(message)s' + fore_colors['RESET'],
            logging.INFO: format + info_color + '%(message)s' + fore_colors['RESET'],
            logging.WARNING:  format + fore_colors['YELLOW'] + '%(message)s' + fore_colors['RESET'],
            logging.ERROR:  format + fore_colors['RED'] + '%(message)s' + fore_colors['RESET'],
            logging.CRITICAL:  format + fore_colors['LIGHT_RED'] + '%(message)s' + fore_colors['RESET'],
            logging.FATAL:  format + fore_colors['LIGHT_RED'] + back_colors['LIGHT_WHITE'] + '%(message)s' + fore_colors['RESET']
        }


    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def init_logging(logger_name, version, log_file_path=None, info_color=None):
    # Initialize colorama
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter(logger_name, version, info_color))
    logger.addHandler(ch)

    if log_file_path:
        if not path.exists(path.dirname(log_file_path)):
            mkdir(path.dirname(log_file_path))
        log_file = logging.FileHandler(log_file_path, mode="a", encoding='utf-8')
        log_file.setLevel(logging.DEBUG)
        log_file.setFormatter(CustomFormatter(logger_name, version))
        logger.addHandler(log_file)

    return logger


if __name__ == '__main__':
    LOGGER_NAME = 'my_log'
    VERSION = '0.0.1'
    LOG_OUTPUT_PATH = './test/testlog.txt'
    test = init_logging(LOGGER_NAME, VERSION, log_file_path=LOG_OUTPUT_PATH, info_color='RED')
    test.debug("debug message")
    test.info("info message")
    test.warning("info message")
    test.error("error message")
    test.critical("critical message")
    test.fatal("fatal message")