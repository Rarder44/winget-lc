import configparser

class Settings(object):
  def __new__(cls):
    if not hasattr(cls, 'instance'):
        cls.instance = super(Settings, cls).__new__(cls)
        cls.config = configparser.ConfigParser()
        cls.config.read('config.ini')
        cls.workFolder="tmp"

        cls.cerPublisher = f'CN={Settings().config["certificate"]["CN"]}, O={Settings().config["certificate"]["O"]}, C={Settings().config["certificate"]["C"]}'
        cls.misc={}
        
    return cls.instance