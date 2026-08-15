Feature: Interactive knowledge graph viewer
  As a visitor exploring the wiki
  I want the graph page to ship with the back-to-site link + site_url
  payload so clicks never land on a 404.

  Background:
    Given a built llmwiki site on disk

  Scenario: Graph viewer has back-to-site link (#268)
    When I visit the graph page
    Then the "Home" back-link is visible

  Scenario: Graph click handler reads site_url (#331)
    When I visit the graph page
    Then the graph JSON payload contains "site_url"
