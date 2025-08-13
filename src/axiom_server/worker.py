
from dataclasses import dataclass
import logging
import random
import sys

from axiom_server.crucible import CrucibleFactAdder, extract_facts_from_text
from axiom_server.discovery_rss import RSS_FEEDS, fetch_new_content
from axiom_server.p2p.node import Node, NodeCoroutine
from axiom_server.ledger import SessionMaker


logger = logging.getLogger("node-worker")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

fact_gatherer_logger = logging.getLogger("node-worker.fact-gatherer")


def fact_gatherer(rss_feed_url: str) -> NodeCoroutine:
	fact_gatherer_logger.info(f"gathering facts from '{rss_feed_url}'")

	with SessionMaker() as session:
		adder = CrucibleFactAdder(session)

		for text_content in fetch_new_content(rss_feed_url):
			for fact in extract_facts_from_text(text_content):
				session.add(fact)
				session.commit()
				adder.add(fact)

			yield

		fact_gatherer_logger.info(f"facts gathered: {adder.addition_count} facts added, {adder.contradiction_count} facts contradicted, {adder.corroboration_count} facts corroborated")		


def rss_feed_elector(node: Node) -> NodeCoroutine:
	while True:
		rss_feed_url = random.choice(RSS_FEEDS)
		node.add_process("fact-gatherer", fact_gatherer(rss_feed_url))
		yield
