import logging

# basic logging turned on 
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
LOGGER = logging.getLogger(__name__)