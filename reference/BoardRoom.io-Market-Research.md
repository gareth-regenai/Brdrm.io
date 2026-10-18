# Board Pack SaaS: Market Research

2026-10-15 · Alex Cooper

## Summary

The market is real but modest: roughly 25,000 to 55,000 UK companies have outside investors (my estimate, midpoint 40,000), worth about £24m to £72m a year at the midpoint and £50 to £150 a month per company.

- **Realistic reach:** about 12,000 companies are plausibly in scope, or £7m to £22m a year. This assumes 30% have 10+ staff and an investor who wants regular packs, which still needs testing.
- **Who pays:** both models work. Investor-pays is proven by Standard Metrics, and founder-pays is faster to start. A hybrid, where an investor sponsors and founders upgrade, fits best.
- **Competition:** investor-update and portfolio tools (Visible, Standard Metrics, Vestberry) are established, and board-pack automation tools (Rima, Boardbrief AI) are emerging. The gap is multi-department board packs from CSVs for angel-backed companies.
- **Main risks:** the moat is thin because a Claude skill can do part of this, TAM is not paying customers, and nobody publishes a count of angel-backed companies.

## The product

Each department uploads a CSV and the company gets one formatted board pack for its investors.

- **Origin:** an angel investor asked to see a company's board and wanted a place where venture teams upload CSVs that are formatted for him.
- **MVP (proposed):** one CSV template per department (sales, product, finance, people), plus a column-mapping step that remembers each team's layout so they do not have to change how they export.
- **Workflow (from the mockup):** department leads edit their own sections, the CEO approves each cycle, and investors see only approved cycles in a read-only view.
- **Calculated figures:** headline numbers such as runway, burn and pipeline coverage are calculated from the uploads, not typed in.

## Market size

The addressable market (TAM) is the stock of companies that exist with outside investors, not the ones that raised this year, and for the UK it comes to roughly 25,000 to 55,000 companies. That range is my own triangulation, because nobody publishes the figure.

| Approach | Figure | Reading |
|---|---|---|
| [Beauhurst tracked companies](https://beauhurst.com/blog/how-to-build-top-startup-lists) | 32,000+ high-growth companies; another source says 50,000+ | A stock of ambitious companies, but not all have investors |
| [SME equity use](https://leasinglife.com/?p=10366) | 1% of SMEs used equity in a three-year window (2015 survey); about 55,000 on [5.5m private-sector businesses](https://www.bytestart.co.uk/?p=30005) | Old survey and a base full of tiny firms, so a sanity check only |
| [S/EIS raises](https://www.eisa.org.uk/hmrc-key-statistics-2026/) | 3,735 EIS and 2,430 SEIS companies raised in 2024-25; about 2,900 are new each year | A flow: five years of new entrants is about 14,500 before failures, and with VC-backed companies the pool is roughly 15,000 to 25,000, which is a floor |

VC-fund counts understate it badly. The BVCA's [9,000 VC-backed businesses](https://www.privateequitywire.co.uk/uk-vc-activity-hits-9bn-in-2024-bvca-reports/) exclude angel-backed companies, individual investors and overseas investors. The market is also not UK-only: 29% of announced UK equity deals in 2021 [involved an overseas investor](https://www.british-business-bank.co.uk/about/research-and-publications/small-business-equity-tracker-2022-report/summary), and the US had [69,060 ventures](https://www.eban.org/?p=34928) take angel funding in 2021 alone.

TAM is not paying customers. The funnel below narrows it to the companies you can sell to and then to the first segment worth approaching.

*[Chart in the live doc: "estimates and assumptions from this document · UK · October 2026" (market funnel). Charts do not export as text; see the live doc.]*

Each stage narrows the pool, and the ICP has no count until the first interviews. Software and AI lead it because information and communication firms took 35% of EIS and 42% of SEIS money in 2024-25 ([HMRC figures](https://www.eisa.org.uk/hmrc-key-statistics-2026/)).

## Who pays

Both models are proven elsewhere, and the best fit is a hybrid where an investor sponsors the tool and founders upgrade for more.

| Model | Evidence | Price anchor | Main risk |
|---|---|---|---|
| Investor pays | [Standard Metrics](https://intercom.help/standardmetrics/en/articles/4600342-faqs) is paid for by investment firms and free for portfolio companies, which need an investor invite. Companies often [report to several investors](https://standardmetrics.io/library/why-founder-friendly-software-for-vc-firms-matters-in-2025/), which spreads it. | [Visible](https://visible.vc/investor-pricing/) investor plans are custom-priced by portfolio size. [Dealum](https://dealum.com/pricing/network) angel networks pay $119 to $719 a month for 50 to 500 members. | The investor needs enough portfolio companies to justify a fee |
| Founder pays | [Visible founder plans](https://visible.vc/pricing/) are free, then $59, $129 and $199 a month. Small-team [board portals](https://boardable.com/plans/) such as Boardable run $20.99 to $35.99 per user a month. | £50 to £150 a month per company (working band) | Free competitor if the founder's investors already use Standard Metrics |
| Hybrid | Investor or syndicate lead sponsors and invites. Founders get a basic free version and pay for multi-department packs and extra investors. | Platform fee per investor plus a founder upgrade | The invite flow has to work for an individual with no firm account |

An individual angel is unlikely to pay more than the $39 a month Dealum charges for Investor Plus, so sponsors need a larger portfolio. That points to syndicate leads, solo capitalists and funds as payers, and to founders as the fallback payer.

## Buyer segments

The best sponsors are investors with 10 or more companies and no reporting back office: syndicate leads, solo capitalists and venture studios. By the usual definition an individual investing their own money is an angel, not a VC, so they drop out of fund-based counts even when they act like a VC.

| Segment | Evidence | Fit as sponsor |
|---|---|---|
| [Angel networks and syndicates](https://www.beauhurst.com/blog/top-angel-networks-uk) | 2,046 fundraisings involving angel networks from 2011 to 2021. Scotland alone has [around 20 syndicates](https://www.ellty.com/investors/edinburgh-angel-investors). Operators [consolidate and share updates](https://thediligentobserver.substack.com/p/whats-the-news?open=false) for members. | High |
| [Solo capitalists and solo GPs](https://ewvc.beehiiv.com/p/ewvc-march-newsletter-the-solo-gp) | 53.4% of emerging European VC funds launched in 2024 were solo-GP led. They run lean with no back office. | High |
| [Venture studios and holding groups](https://www.goingvc.com/post/the-rise-of-venture-studios) | 1,100+ studios founded worldwide. They run several ventures each. | High |
| [Individual angels](https://www.eban.org/wp-content/uploads/2025/12/Stats-Compendium-2024.pdf) | About 47,600 network-affiliated angels in Europe and 66,000 in the US. The [Center for Venture Research](https://www.eban.org/?p=34928) counted 363,460 active US angels in 2021. | Low as payers (few companies each), good as invitees |
| [VC and PE funds](https://about.beauhurst.com/blog/top-private-equity-venture-capital-firms-in-uk/) | 599 active UK PE and VC funds. Already served by Visible and Standard Metrics. | Medium, little differentiation |
| [Accelerators and incubators](https://www.uktech.news/tech-hubs/uk-startup-accelerators-incubators-doubled-20220905) | About 750 in the UK in 2022, many reliant on public funding. | Medium |
| [Family offices](https://g2.com/products/vestberry/pricing) | A small family office reviewing Vestberry wanted a lighter version at a lower price. | Medium |

## Competitors

No tool found does multi-department CSV to board pack for angel-backed companies. The closest sit in four groups: investor-update tools, portfolio monitoring, board portals and board-pack automation.

| Tool | Buyer | What it does |
|---|---|---|
| [Visible](https://visible.vc/pricing/) | Investors and founders | Collects portfolio metrics and sends investor updates |
| [Standard Metrics](https://intercom.help/standardmetrics/en/articles/4600342-faqs) | Investment firms; free for companies | Data collection, benchmarking, Xero and QuickBooks sync |
| [Carta Investor Services](https://blog.carta.com/carta-investor-services/) | Funds | Portfolio tracking inside the equity platform |
| [Vestberry](https://www.capterra.co.uk/software/181027/vestberry) | VC, PE, family offices, angels | Portfolio monitoring and reporting |
| [Dealum Investor Plus](https://dealum.com/solutions/investor) | Active angels | Tracks founder updates across companies |
| [Quantro](https://www.hunted.space/product/quantro-2) | Founders and angels | Structured updates, portfolio dashboard, shared data room |
| [Rima](https://getrima.ai/reporting/board-pack-automation) | Finance teams | Fills your own Excel board pack template from source data in 3 hours |
| [Boardbrief AI](https://www.startuphub.ai/startups/boardbriefai) | PE-backed portfolio companies | Automates board decks |
| [board-deck-builder skill](https://agentskillsfinder.com/skills/board-deck-builder) | Anyone | Free open-source Claude skill for board decks |
| [Boardable](https://boardable.com/plans/) | Small boards | Meeting management and documents |
| [Zeck](https://costbench.com/software/board-management/compare-all/) | Startups and portfolio companies | Board meeting software with AI automation |
| [Diligent Boards](https://costbench.com/software/board-management/compare-all/) | Large organisations | Board portal |

The moat is thin: a free skill already covers part of the job, so distribution through investors and the multi-department workflow matter more than the formatting.

Pricing, tiers and features for each tool are in the separate document "Competitor Pricing and Tiers" (BoardRoom.io-Competitor-Pricing-and-Tiers.md).

## Risks and open questions

The biggest risk is that the market looks large on paper but the paying segment is small and the product is easy to copy.

- **Thin moat:** a free Claude skill and board-pack automation tools cover part of the formatting. The value is in the multi-department workflow, the approval step and distribution through investors.
- **TAM is not customers:** the 25,000 to 55,000 range is my estimate, and the 30% SAM share is an untested assumption.
- **No published count of angel-backed companies:** Companies House share data or a Beauhurst purchase could replace the estimate.
- **Free competitor:** Standard Metrics is free for companies whose investor already uses it.
- **Pricing evidence is soft:** Zeck and Diligent prices come from third-party comparison sites, and Standard Metrics, Vestberry and Carta do not publish theirs.
- **Sensitive data:** department exports can carry salaries or personal data, so the upload step needs to redact or exclude those columns.
- **International from day one:** investors and companies span countries, so currencies and data residency need an answer.

Open question: does the angel who asked for this back 10 or more companies, and does he already ask them for regular reports? That is the quickest test of the investor-pays side.

## Next steps

Test demand with real investors before building more, starting with the angel who asked for this.

1. Ask the angel who asked for this how many companies he backs, how he gets reports today and whether he would sponsor a tool.
2. Interview 8 to 10 sponsors with 10 or more companies (syndicate leads, solo capitalists, studios) and a few founders, covering how they get board data and what they would pay.
3. Settle the MVP data model: one CSV template per department plus remembered column mapping.
4. Pilot with two or three friendly companies using the approval flow and read-only investor view.
5. Replace the TAM estimate with a count from Companies House share data or Beauhurst.
6. Test pricing at £50 to £150 a month per company and a per-company sponsor fee.

## Sources

Competitor tiers and prices, checked against vendor pages where possible, are in the separate pricing document. Everything else here comes from web search excerpts rather than fully opened pages, so verify any number before quoting it outside this document. Estimates and assumptions are labelled in the text.

- Market size: [HMRC EIS/SEIS statistics](https://www.eisa.org.uk/hmrc-key-statistics-2026/), [UK VC activity 2024](https://www.privateequitywire.co.uk/uk-vc-activity-hits-9bn-in-2024-bvca-reports/), [BVCA evidence to Parliament](https://committees.parliament.uk/writtenevidence/148707/html/), [Beauhurst on crowdfunding](https://beauhurst.com/blog/uk-equity-crowdfunding), [Beauhurst high-growth companies](https://beauhurst.com/blog/how-to-build-top-startup-lists), [ICAEW on Beauhurst](https://icaew.com/technical/corporate-finance/startups-scaleups-and-venture-capital/curator-of-data), [SME equity use](https://leasinglife.com/?p=10366), [UK business population](https://www.bytestart.co.uk/?p=30005), [Companies House register](https://www.gov.uk/government/statistics/companies-register-activities-statistical-release-april-2025-to-march-2026/companies-register-activities-statistical-release-april-2025-to-march-2026), [ScaleUp Annual Review](https://www.genglobal.org/gen-research/news/chancellor-welcomes-10th-scaleup-report-identifies-record-44595-scaleups-uk), [British Business Bank equity tracker](https://www.british-business-bank.co.uk/about/research-and-publications/small-business-equity-tracker-2022-report/summary)
- Investors: [EBAN statistics 2024](https://www.eban.org/wp-content/uploads/2025/12/Stats-Compendium-2024.pdf), [Center for Venture Research via EBAN](https://www.eban.org/?p=34928), [Beauhurst angel networks](https://www.beauhurst.com/blog/top-angel-networks-uk), [Edinburgh angels](https://www.ellty.com/investors/edinburgh-angel-investors), [angel network operators](https://thediligentobserver.substack.com/p/whats-the-news?open=false), [solo GPs in Europe](https://ewvc.beehiiv.com/p/ewvc-march-newsletter-the-solo-gp), [venture studios](https://www.goingvc.com/post/the-rise-of-venture-studios), [UK PE and VC funds](https://about.beauhurst.com/blog/top-private-equity-venture-capital-firms-in-uk/), [UK accelerators](https://www.uktech.news/tech-hubs/uk-startup-accelerators-incubators-doubled-20220905)
- Competitors and pricing: [portfolio monitoring tools](https://vcbeast.com/best-portfolio-monitoring-tools), [investor update tools](https://valueaddvc.com/blog/top-8-investor-update-tools-for-founders-what-each-does-and-which-is-worth-paying-for), [Standard Metrics FAQ](https://intercom.help/standardmetrics/en/articles/4600342-faqs), [Standard Metrics on founder-friendly software](https://standardmetrics.io/library/why-founder-friendly-software-for-vc-firms-matters-in-2025/), [Carta Investor Services](https://blog.carta.com/carta-investor-services/), [Vestberry on Capterra](https://www.capterra.co.uk/software/181027/vestberry), [Vestberry reviews](https://g2.com/products/vestberry/pricing), [Dealum](https://blog.dealum.com/investment-monitoring-platform-for-angel-investors-how-to-stay-close-to-whats-really-happening/), [Quantro](https://www.hunted.space/product/quantro-2), [Rima](https://getrima.ai/reporting/board-pack-automation), [Boardbrief AI](https://www.startuphub.ai/startups/boardbriefai), [board-deck-builder skill](https://agentskillsfinder.com/skills/board-deck-builder), [board management pricing](https://costbench.com/software/board-management/compare-all/)
