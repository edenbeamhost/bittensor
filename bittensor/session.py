import argparse
from munch import Munch

from bittensor.synapse import Synapse
from bittensor.dendrite import Dendrite
from bittensor.axon import Axon
from bittensor.metagraph import Metagraph
from bittensor.utils.asyncio import Asyncio
from bittensor.subtensor import Keypair
from bittensor.tb_logger import TBLogger
from loguru import logger
import asyncio


class FailedConnectToChain(Exception):
    pass

class FailedSubscribeToChain(Exception):
    pass

class FailedToEnterSession(Exception):
    pass

class FailedToPollChain(Exception):
    pass

class BTSession:
    def __init__(self, config, keypair: Keypair):
        self.config = config 
        self.__keypair = keypair
        self.metagraph = Metagraph(self.config, self.__keypair)
        self.axon = Axon(self.config, self.__keypair)
        self.dendrite = Dendrite(self.config, self.__keypair)
        self.tbwriter = TBLogger(self.config)

    @staticmethod   
    def add_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        return parser

    @staticmethod   
    def check_config(config: Munch) -> Munch:
        return config

    def __del__(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.stop())

    def serve(self, synapse: Synapse):
        r""" Serves a Synapse to the axon server replacing the previous Synapse if exists.

            Args:
                synapse (:obj:`bittensor.Synapse`, `required`): 
                    synpase object to serve on the axon server.
        """
        self.axon.serve(synapse)

    def __enter__(self):
        logger.info('session enter')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start())
        return self

    def __exit__(self, *args):
        logger.info('session exit')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.stop())


    async def start(self):
        # Stop background grpc threads for serving the synapse object.
        logger.info('Start axon server...')
        try:
            self.axon.start()
        except Exception as e:
            logger.error('SESSION: Failed to start axon server with error: {}', e)
            raise FailedToEnterSession

        logger.info('Connect to chain ...')
        try:
            connected = await self.metagraph.connect()
            if not connected:
                logger.error('SESSION: Timeout while subscribing to the chain endpoint')
                raise FailedConnectToChain
        except Exception as e:
            logger.error('SESSION: Error while connecting to the chain endpoint: {}', e)
            raise FailedToEnterSession

        logger.info('Subscribe to chain ...')
        try:
            await self.metagraph.subscribe(10)
                # logger.error('SESSION: Timeout while subscribing to the chain endpoint')
                # raise FailedSubscribeToChain
        except Exception as e:
            logger.error('SESSION: Error while subscribing to the chain endpoint: {}', e)
            raise FailedToEnterSession

        logger.info("Starting polling of chain for neurons")

        Asyncio.add_task(self.metagraph.pollchain())

    async def stop(self):
        # Stop background grpc threads for serving synapse objects.
        logger.info('Unsubscribe from chain ...')
        try:
            await self.metagraph.unsubscribe(10)
            # if not self.metagraph.unsubscribe(10):
            #     logger.error('SESSION: Timeout while unsubscribing to the chain endpoint')
        except Exception as e:
            logger.error('SESSION: Error while unsubscribing to the chain endpoint: {}', e)

        logger.info('Stopping axon server..')
        try:
            self.axon.stop()
        except Exception as e:
            logger.error('SESSION: Error while stopping axon server: {} ', e)

        # Stop background grpc threads for serving synapse objects.
        logger.info('Unsubscribe from chain ...')
        try:
            if not self.metagraph.unsubscribe(10):
                logger.error('SESSION: Timeout while unsubscribing to the chain endpoint')
        except Exception as e:
            logger.error('SESSION: Error while unsubscribing to the chain endpoint: {}', e)

    def neurons (self):
       return self.metagraph.neurons()

    def subscribe (self):
       self.metagraph.subscribe()

    def unsubscribe (self):
        self.metagraph.unsubscribe()