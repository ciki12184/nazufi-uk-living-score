# Wix page element IDs

Create a page such as `/uk-living-score` and add the following elements.

## Search
- Input: `#postcodeInput`
- Button: `#analyseButton`
- Text: `#loadingText`
- Text: `#errorText`

## Main result
- Section/box: `#resultsSection`
- Text: `#resultPostcode`
- Text: `#localAuthorityText`
- Text: `#regionText`
- Text: `#scoreStatusText`

## Crime
- Text: `#crimeSummary`
- Repeater: `#crimeRepeater`
  - Text inside repeater: `#crimeCategory`
  - Text inside repeater: `#crimeCount`

## Schools
- Text: `#schoolStatusText`
- Repeater: `#schoolsRepeater`
  - Text: `#schoolName`
  - Text: `#schoolMeta`
  - Text: `#schoolInspection`

## Property sales
- Text: `#salesStatusText`
- Repeater: `#salesRepeater`
  - Text: `#saleMeta`
  - Text: `#salePrice`

## Rent
- Text: `#rentText`

## Recommended static source panel
Include visible source names:
- Police.uk / Home Office
- Ofsted
- HM Land Registry
- Office for National Statistics
- Environment Agency

Include:
- “Latest available published data”
- “No source → No score”
- “No data → No AI guess”
