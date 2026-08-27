# #139 — merge alias resolution

`llmwiki.wikilinks.build_page_alias_map` reads `## Aliases` on each page; `resolve_wikilink_target` maps merged-away names to the survivor slug. Graph, `link_integrity`, backlinks, and references call it before treating a link as broken or attributing an inbound reference. `candidates.merge` refreshes harvest boilerplate counts after unioning evidence.
