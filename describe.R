

my_test <- read_csv("C:/Users/DBT3KD/Desktop/sport_driven_demand/athlete_sponsorship_deals_with_sport.csv")
names(my_test)
my_test %>%
group_by(brand)%>%
summarise(#total_value = sum(total_value, na.rm = TRUE),
			n = n()
		  )%>%
		  arrange(desc(n))

my_test %>%
group_by(category)%>%
summarise(#total_value = sum(total_value, na.rm = TRUE),
			n = n()
		  )%>%
		  arrange(desc(n))

my_test %>%
group_by(sport)%>%
summarise(#total_value = sum(total_value, na.rm = TRUE),
			n = n()
		  )%>%
		  arrange(desc(n))
