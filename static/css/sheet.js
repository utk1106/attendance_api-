async function fetchAndUpdateData() {
    try {
      const response = await fetch('/api/sheet-data');
      const rawData = await response.json();
  
      const formatted = rawData.map(row => ({
        username: row['Employee Name'],
        date: row['Date'],
        login_time: row['Login Time'],
        logout_time: row['Logout Time'],
        place: row['Location']
      }));
  
      console.log('Formatted data:', formatted);
      hot.loadData(formatted);
    } catch (error) {
      console.error('Error fetching updated data:', error);
    }
  }
  