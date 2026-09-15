import { getAreaReport, getDataFreshness } from 'backend/livingScore.web';

$w.onReady(function () {
  $w('#resultsSection').collapse();
  $w('#errorText').collapse();
  $w('#loadingText').collapse();

  $w('#analyseButton').onClick(async () => {
    const postcode = String($w('#postcodeInput').value || '').trim();

    $w('#errorText').collapse();
    $w('#resultsSection').collapse();
    $w('#loadingText').text = 'Loading the latest available public data…';
    $w('#loadingText').expand();
    $w('#analyseButton').disable();

    try {
      const result = await getAreaReport(postcode);

      if (!result?.ok) {
        $w('#errorText').text =
          result?.message ||
          'Validated data is unavailable for this postcode.';
        $w('#errorText').expand();
        return;
      }

      renderReport(result.report);
      $w('#resultsSection').expand();
    } catch (error) {
      $w('#errorText').text =
        'The data service is temporarily unavailable. No values were estimated.';
      $w('#errorText').expand();
    } finally {
      $w('#loadingText').collapse();
      $w('#analyseButton').enable();
    }
  });
});

function valueOrUnavailable(value) {
  if (value === null || value === undefined || value === '') {
    return 'Unavailable';
  }
  return String(value);
}

function renderReport(report) {
  $w('#resultPostcode').text = valueOrUnavailable(report?.postcode);
  $w('#localAuthorityText').text =
    valueOrUnavailable(report?.area?.admin_district);
  $w('#regionText').text =
    valueOrUnavailable(report?.area?.region);

  renderCrime(report?.crime);
  renderSchools(report?.schools);
  renderPropertySales(report?.property_sales);
  renderRent(report?.private_rent);

  $w('#scoreStatusText').text =
    report?.overall_score?.status === 'withheld'
      ? 'Overall score withheld until the full methodology and benchmark set are validated.'
      : valueOrUnavailable(report?.overall_score?.status);
}

function renderCrime(crime) {
  if (!crime || crime.status === 'unavailable') {
    $w('#crimeSummary').text = 'Crime data unavailable.';
    $w('#crimeRepeater').data = [];
    return;
  }

  $w('#crimeSummary').text =
    `${crime.incident_count} recorded incidents • ${crime.data_month}`;

  const rows = (crime.categories || []).slice(0, 8).map((item, index) => ({
    _id: `crime-${index}`,
    category: item.category,
    count: String(item.incident_count)
  }));

  $w('#crimeRepeater').data = rows;
  $w('#crimeRepeater').onItemReady(($item, itemData) => {
    $item('#crimeCategory').text = valueOrUnavailable(itemData.category);
    $item('#crimeCount').text = valueOrUnavailable(itemData.count);
  });
}

function renderSchools(schools) {
  if (!schools || schools.status === 'unavailable') {
    $w('#schoolsRepeater').data = [];
    $w('#schoolStatusText').text = 'Validated school data unavailable.';
    return;
  }

  $w('#schoolStatusText').text =
    `Nearby schools within ${schools.radius_km} km`;

  const rows = (schools.items || []).map((school, index) => ({
    _id: `school-${index}`,
    name: school.school_name,
    meta: [
      school.phase,
      school.distance_km !== undefined ? `${school.distance_km} km` : null
    ].filter(Boolean).join(' • '),
    inspection: school.overall_effectiveness || 'See inspection data'
  }));

  $w('#schoolsRepeater').data = rows;
  $w('#schoolsRepeater').onItemReady(($item, itemData) => {
    $item('#schoolName').text = valueOrUnavailable(itemData.name);
    $item('#schoolMeta').text = valueOrUnavailable(itemData.meta);
    $item('#schoolInspection').text = valueOrUnavailable(itemData.inspection);
  });
}

function renderPropertySales(propertySales) {
  if (!propertySales || propertySales.status === 'unavailable') {
    $w('#salesRepeater').data = [];
    $w('#salesStatusText').text = 'Validated property sales data unavailable.';
    return;
  }

  $w('#salesStatusText').text =
    propertySales.scope === 'exact_postcode'
      ? 'Recent registered sales for this postcode'
      : 'Recent registered sales for the outward postcode area';

  const rows = (propertySales.items || []).slice(0, 10).map((sale, index) => ({
    _id: `sale-${index}`,
    date: sale.transfer_date,
    type: sale.property_type || '',
    price: Number.isFinite(Number(sale.price))
      ? `£${Number(sale.price).toLocaleString('en-GB')}`
      : 'Unavailable'
  }));

  $w('#salesRepeater').data = rows;
  $w('#salesRepeater').onItemReady(($item, itemData) => {
    $item('#saleMeta').text =
      [itemData.date, itemData.type].filter(Boolean).join(' • ');
    $item('#salePrice').text = valueOrUnavailable(itemData.price);
  });
}

function renderRent(privateRent) {
  if (!privateRent || privateRent.status === 'unavailable') {
    $w('#rentText').text = 'Validated ONS private-rent data unavailable.';
    return;
  }

  const item = privateRent.item;
  const amount = Number.isFinite(Number(item?.average_monthly_rent))
    ? `£${Number(item.average_monthly_rent).toLocaleString('en-GB')} / month`
    : 'Unavailable';

  $w('#rentText').text =
    `${amount} • ${valueOrUnavailable(item?.area_name)} • ${valueOrUnavailable(item?.period)}`;
}
