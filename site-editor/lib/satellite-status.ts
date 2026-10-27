export function satelliteStatusLabel(status:string|undefined,marathi:boolean){
  const labels:Record<string,[string,string]>={
    REFRESHED:['Imagery refreshed','उपग्रह प्रतिमेतून अद्ययावत'],
    NO_COORDINATES_OR_OUTLINE:['Coordinates / outline missing','स्थान / सीमा अनुपलब्ध'],
    INVALID_COORDINATES:['Coordinates need review','स्थानाची पडताळणी आवश्यक'],
    INVALID_OUTLINE:['Outline needs review','सीमेची पडताळणी आवश्यक'],
    INSUFFICIENT_CLEAR_PIXELS:['Too few clear pixels; previous estimate retained','स्वच्छ पिक्सेल अपुरे; पूर्वीचा अंदाज कायम'],
    FETCH_FAILED:['Image retrieval failed; previous estimate retained','प्रतिमा मिळाली नाही; पूर्वीचा अंदाज कायम'],
  };
  return status?(labels[status]?.[marathi?1:0]||status):'';
}
