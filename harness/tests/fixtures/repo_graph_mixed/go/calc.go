package calc

type Runner interface {
	Run(value int) int
}

type Service struct{}

func (Service) Run(value int) int {
	return value + 1
}
